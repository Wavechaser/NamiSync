"use strict";

const FAILURE_TYPES = Object.freeze(new Set([
  "AbortError",
  "Error",
  "RangeError",
  "ReferenceError",
  "SecurityError",
  "SyntaxError",
  "TypeError",
]));
let galleryStage = "module_import";
let galleryMeasurementStep = "not_started";
let galleryFailureReason = "stage_failure";
let gallerySettled = false;
let galleryWatchdog = null;
const PSEUDO_STATE_SETTLE_MS = 350;
const CONTROL_REPORT_CHUNK_ROWS = 10;

function validAccepted(value) {
  return value !== null &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    Object.keys(value).length === 1 &&
    value.accepted === true;
}

function validMinimumWindowStatus(value) {
  if (value === null || typeof value !== "object" || Array.isArray(value)
      || typeof value.complete !== "boolean") return false;
  if (!value.complete) return Object.keys(value).length === 1;
  return Object.keys(value).length === 8
    && [
      "owner_scale", "minimum_width", "minimum_height",
      "outer_width", "outer_height", "client_width", "client_height",
    ].every((name) => Number.isFinite(value[name]) && value[name] > 0);
}

function validNativeFailureSnapshot(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    && Object.keys(value).length === 8
    && ["none", "pseudo_states", "wheel_content", "wheel_backdrop", "minimum_window"]
      .includes(value.pending)
    && [
      "owner_scale", "minimum_width", "minimum_height", "outer_width",
      "outer_height", "client_width", "client_height",
    ].every((name) => Number.isFinite(value[name]) && value[name] > 0);
}

function minimumWindowSettled(value, innerWidth, innerHeight) {
  return validMinimumWindowStatus(value) && value.complete
    && Math.abs(value.outer_width - value.minimum_width) <= 1
    && Math.abs(value.outer_height - value.minimum_height) <= 1
    && Math.abs(value.client_width / value.owner_scale - innerWidth) <= 2
    && Math.abs(value.client_height / value.owner_scale - innerHeight) <= 2;
}

async function waitForTheme(theme) {
  for (let frame = 0; frame < 120; frame += 1) {
    if (document.documentElement.dataset.theme === theme) {
      return;
    }
    await new Promise((resolve) => requestAnimationFrame(resolve));
  }
  throw new Error("the seeded cosmetic theme did not reach the page");
}

async function waitForThemeSelector(root, theme, disabled) {
  for (let frame = 0; frame < 300; frame += 1) {
    const trigger = root.querySelector(".nami-combobox__trigger");
    if (
      trigger instanceof HTMLButtonElement
      && root.dataset.value === theme
      && trigger.disabled === disabled
    ) {
      return;
    }
    await new Promise((resolve) => requestAnimationFrame(resolve));
  }
  throw new Error("the product theme selector did not reconcile");
}

function buildFailureEvidence(stage, type, step, reason, native = null) {
  const failure = { stage, type, step, reason };
  if (native !== null) failure.native = Object.freeze({ ...native });
  return Object.freeze(failure);
}

async function reportFailure(error) {
  if (gallerySettled) return;
  gallerySettled = true;
  if (galleryWatchdog !== null) clearTimeout(galleryWatchdog);
  const candidate = error !== null && typeof error === "object" ? error.name : "";
  const type = FAILURE_TYPES.has(candidate) ? candidate : "Error";
  let native = null;
  const nativeFailure = [
    "native_pseudo_pending",
    "native_wheel_pending",
    "native_minimum_pending",
    "native_minimum_dimensions",
  ].includes(galleryFailureReason);
  let dispatchInteractive;
  try {
    ({ dispatchInteractive } = await import("/bridge.js"));
  } catch {
    dispatchInteractive = null;
  }
  if (nativeFailure && typeof dispatchInteractive === "function") {
    try {
      native = await dispatchInteractive(
        "test_report",
        Object.freeze({ phase: "diagnostic_status" }),
        validNativeFailureSnapshot,
      );
    } catch {
      galleryFailureReason = "stage_failure";
    }
  }
  const failure = buildFailureEvidence(
    galleryStage, type, galleryMeasurementStep, galleryFailureReason,
    native,
  );
  if (typeof dispatchInteractive === "function") {
    try {
      await dispatchInteractive(
        "test_report",
        Object.freeze({ phase: "failure", failure }),
        validAccepted,
      );
    } catch {
      // Preserve the closed location even if optional diagnostic detail drifted.
      try {
        await dispatchInteractive(
          "test_report",
          Object.freeze({
            phase: "failure",
            failure: buildFailureEvidence(
              galleryStage, type, galleryMeasurementStep, "stage_failure",
            ),
          }),
          validAccepted,
        );
      } catch {
        // The native scenario deadline remains authoritative when transport is gone.
      }
    }
  }
  const target = document.querySelector("#host-status");
  if (target instanceof HTMLElement) {
    target.textContent = `Gallery failed: ${type}`;
  }
}

window.addEventListener("error", (event) => { void reportFailure(event.error); });
window.addEventListener("unhandledrejection", (event) => {
  void reportFailure(event.reason);
});

(async () => {

  const TEST_ONLY_GALLERY_MARKER =
    "NAMISYNC_TEST_ONLY_COMPONENT_GALLERY_5CE45567A17F4D74";
  const TEST_ONLY_PLAN_ROW_MARKER =
    "NAMISYNC_TEST_ONLY_PLAN_ROWS_45C8C53D55D34893";
  const TEST_ONLY_INTEGRITY_ROW_MARKER =
    "NAMISYNC_TEST_ONLY_INTEGRITY_ROWS_7A26DB6506CC49D8";
  const LIFECYCLE_CASES = Object.freeze([
    { key: "new", text: "New", hue: "neutral", form: "text", icon: "info", shape: "circle-info", cue: "Not started" },
    { key: "planned", text: "Planned", hue: "neutral", form: "text", icon: "info", shape: "circle-info", cue: "Plan is ready" },
    { key: "queued", text: "Queued", hue: "neutral", form: "text", icon: "info", shape: "clock", cue: "Waiting to start" },
    { key: "executing", text: "Executing", hue: "accent", form: "text", icon: "info", shape: "arrow-right", cue: "Sync is running" },
    { key: "verifying", text: "Verifying", hue: "accent", form: "text", icon: "info", shape: "circle-info", cue: "Verification is running" },
    { key: "completed", text: "Completed", hue: "green", form: "text", icon: "checkmark-circle", shape: "circle-check", cue: "Finished successfully" },
    { key: "partial", text: "Partial", hue: "yellow", form: "text", icon: "warning", shape: "triangle", cue: "Some work needs review" },
    { key: "degraded", text: "Degraded", hue: "yellow", form: "text", icon: "warning", shape: "triangle", cue: "Completed with degraded items" },
    { key: "incomplete", text: "Incomplete", hue: "yellow", form: "text", icon: "warning", shape: "triangle", cue: "Not all work finished" },
    { key: "pausing", text: "Pausing", hue: "accent", form: "text", icon: "info", shape: "pause", cue: "Pause is in progress" },
    { key: "canceling", text: "Canceling", hue: "accent", form: "text", icon: "info", shape: "circle-x", cue: "Cancellation is in progress" },
    { key: "paused", text: "Paused", hue: "yellow", form: "text", icon: "warning", shape: "pause", cue: "Resume is available" },
    { key: "interrupted", text: "Interrupted", hue: "yellow", form: "text", icon: "warning", shape: "triangle", cue: "Recoverable interruption" },
    { key: "canceled", text: "Canceled", hue: "neutral", form: "fill", icon: "dismiss-circle", shape: "circle-x", cue: "Stopped without an attention condition" },
    { key: "canceled_after_publish", text: "Canceled after publish", hue: "yellow", form: "fill", icon: "warning", shape: "triangle", cue: "Published filesystem results need review" },
    { key: "canceled_after_mutation", text: "Canceled after mutation", hue: "yellow", form: "fill", icon: "warning", shape: "triangle", cue: "Filesystem mutations need review" },
    { key: "refused", text: "Refused", hue: "yellow", form: "fill", icon: "warning", shape: "barrier", cue: "A precondition needs attention" },
    { key: "capacity", text: "Needs target space", hue: "yellow", form: "fill", icon: "warning", shape: "triangle", cue: "Execution stopped for target capacity" },
    { key: "failed", text: "Failed", hue: "red", form: "fill", icon: "dismiss-circle", shape: "circle-x", cue: "The run failed" },
    { key: "errored", text: "Errored", hue: "red", form: "fill", icon: "dismiss-circle", shape: "circle-x", cue: "The run encountered an error" },
  ]);
  const INTENT_CASES = Object.freeze([
    { key: "copy", text: "Copy", hue: "blue", form: "text", icon: "info", shape: "arrow-right", cue: "New file" },
    { key: "mkdir", text: "Create folder", hue: "blue", form: "text", icon: "checkmark-circle", shape: "folder-plus", cue: "New folder" },
    { key: "move", text: "Move", hue: "purple", form: "text", icon: "info", shape: "paired-arrows", cue: "Relocate" },
    { key: "recase", text: "Recase", hue: "purple", form: "text", icon: "info", shape: "letter-case", cue: "Change name casing" },
    { key: "update", text: "Update", hue: "yellow", form: "text", icon: "info", shape: "refresh", cue: "Replace content" },
    { key: "move_update", text: "Move + update", hue: "yellow", form: "text", icon: "info", shape: "paired-refresh", cue: "Relocate and replace" },
    { key: "trash", text: "Move to trash", hue: "red", form: "text", icon: "warning", shape: "trash", cue: "Recoverable removal" },
    { key: "delete", text: "Delete", hue: "red", form: "fill", icon: "dismiss-circle", shape: "trash-x", cue: "Permanent removal" },
    { key: "noop", text: "No change", hue: "neutral", form: "text", icon: "info", shape: "dash", cue: "No operation" },
    { key: "error", text: "Error", hue: "yellow", form: "fill", icon: "warning", shape: "triangle", cue: "Planning error" },
    { key: "unsupported", text: "Unsupported", hue: "yellow", form: "fill", icon: "warning", shape: "barrier", cue: "Unsupported entry type" },
    { key: "blocked", text: "Blocked", hue: "yellow", form: "fill", icon: "warning", shape: "barrier", cue: "Plan entry is blocked" },
  ]);
  const PLAN_ROW_CASES = Object.freeze([
    { key: "plain", rowView: Object.freeze({ checked: true, mixed: false, selectionDisabled: false, selectionLabel: "Select readme.txt", depth: 0, folder: false, expanded: false, nameText: "readme.txt", sizeText: "1.2 KB", intentText: "—", intentKey: "", checksumText: "5a2f8c10", notesText: "Plain projected file row." }) },
    { key: "mkdir", rowView: Object.freeze({ checked: false, mixed: true, selectionDisabled: false, selectionLabel: "Select photos folder", depth: 0, folder: true, expanded: true, nameText: "photos", sizeText: "14.8 MB", intentText: "Create folder", intentKey: "mkdir", checksumText: "—", notesText: "Partially selected folder." }) },
    { key: "copy", parentKey: "mkdir", rowView: Object.freeze({ checked: true, mixed: false, selectionDisabled: false, selectionLabel: "Select photos DSC_1000.jpeg", depth: 1, folder: false, expanded: false, nameText: "DSC_1000.jpeg", sizeText: "8.1 MB", intentText: "Copy", intentKey: "copy", checksumText: "12ab34cd", notesText: "New child file." }) },
    { key: "update", parentKey: "mkdir", rowView: Object.freeze({ checked: false, mixed: false, selectionDisabled: false, selectionLabel: "Select photos DSC_1001.jpeg", depth: 1, folder: false, expanded: false, nameText: "DSC_1001.jpeg", sizeText: "6.7 MB", intentText: "Update", intentKey: "update", checksumText: "90ef12ab", notesText: "Changed child file." }) },
    { key: "copying", rowView: Object.freeze({ checked: true, mixed: false, selectionDisabled: false, selectionLabel: "Select active-copy.bin", depth: 0, folder: false, expanded: false, nameText: "active-copy.bin", sizeText: "24 MB", intentText: "Copying", intentKey: "", lifecycleKey: "executing", progressPercent: 42, checksumText: "—", notesText: "Projected execution is in progress." }) },
    { key: "completed", rowView: Object.freeze({ checked: true, mixed: false, selectionDisabled: false, selectionLabel: "Select completed-copy.bin", depth: 0, folder: false, expanded: false, nameText: "completed-copy.bin", sizeText: "12 MB", intentText: "Completed", intentKey: "", lifecycleKey: "completed", checksumText: "5a2f8c10", notesText: "Projected execution completed." }) },
    { key: "capacity", rowView: Object.freeze({ checked: true, mixed: false, selectionDisabled: true, selectionLabel: "Selection unavailable for capacity.bin", depth: 0, folder: false, expanded: false, nameText: "capacity.bin", sizeText: "0 B", intentText: "Failed", intentKey: "", lifecycleKey: "capacity", checksumText: "—", notesText: "Operation: Failed (Disk capacity) · Automatic verification: Verified · Stored evidence: Unrecorded" }) },
    { key: "move", rowView: Object.freeze({ checked: true, mixed: false, selectionDisabled: false, selectionLabel: "Select report.pdf", depth: 0, folder: false, expanded: false, nameText: "report.pdf", sizeText: "842 KB", intentText: "Move", intentKey: "move", checksumText: "3456cdef", notesText: "Relocate without replacing bytes." }) },
    { key: "move_update", rowView: Object.freeze({ checked: true, mixed: false, selectionDisabled: false, selectionLabel: "Select notes.md", depth: 0, folder: false, expanded: false, nameText: "notes.md", sizeText: "4.6 KB", intentText: "Move + update", intentKey: "move_update", checksumText: "7890abcd", notesText: "Relocate and replace content." }) },
    { key: "recase", rowView: Object.freeze({ checked: true, mixed: false, selectionDisabled: false, selectionLabel: "Select Logo.PNG", depth: 0, folder: false, expanded: false, nameText: "Logo.PNG", sizeText: "32 KB", intentText: "Recase", intentKey: "recase", checksumText: "bcde1234", notesText: "Change only the path casing." }) },
    { key: "trash", rowView: Object.freeze({ checked: false, mixed: false, selectionDisabled: false, selectionLabel: "Select export.zip", depth: 0, folder: false, expanded: false, nameText: "export.zip", sizeText: "2.4 MB", intentText: "Move to trash", intentKey: "trash", checksumText: "def05678", notesText: "Recoverable removal specimen." }) },
    { key: "delete", rowView: Object.freeze({ checked: false, mixed: false, selectionDisabled: false, selectionLabel: "Select obsolete.tmp", depth: 0, folder: false, expanded: false, nameText: "obsolete.tmp", sizeText: "128 B", intentText: "Delete", intentKey: "delete", checksumText: "1357ace0", notesText: "Permanent removal specimen." }) },
    { key: "noop", rowView: Object.freeze({ checked: false, mixed: false, selectionDisabled: false, selectionLabel: "Select unchanged.bin", depth: 0, folder: false, expanded: false, nameText: "unchanged.bin", sizeText: "16 MB", intentText: "No change", intentKey: "noop", checksumText: "2468bdf1", notesText: "No operation is intended." }) },
    { key: "error", rowView: Object.freeze({ checked: false, mixed: false, selectionDisabled: true, selectionLabel: "Selection unavailable for locked.dat", depth: 0, folder: false, expanded: false, nameText: "locked.dat", sizeText: "—", intentText: "Error", intentKey: "error", checksumText: "—", notesText: "The projected row reports a read error." }) },
    { key: "unsupported", rowView: Object.freeze({ checked: false, mixed: false, selectionDisabled: true, selectionLabel: "Selection unavailable for device-link", depth: 0, folder: false, expanded: false, nameText: "device-link", sizeText: "—", intentText: "Unsupported", intentKey: "unsupported", checksumText: "—", notesText: "Unsupported entry type." }) },
    { key: "blocked", rowView: Object.freeze({ checked: false, mixed: false, selectionDisabled: true, selectionLabel: "Selection unavailable for pending.dat", depth: 0, folder: false, expanded: false, nameText: "pending.dat", sizeText: "—", intentText: "Blocked", intentKey: "blocked", checksumText: "—", notesText: "A planning precondition blocked this entry." }) },
  ]);
  const INTEGRITY_ROW_CASES = Object.freeze([
    { key: "folder", rowView: Object.freeze({ checked: false, mixed: true, selectionDisabled: false, selectionLabel: "Select documents folder", depth: 0, folder: true, expanded: true, nameText: "documents", sizeText: "2.5 MB", presenceText: "Unverified", presenceStatus: "unverified", checksumText: "—", notesText: "Partially selected folder rollup." }) },
    { key: "verified", parentKey: "folder", rowView: Object.freeze({ checked: true, mixed: false, selectionDisabled: false, selectionLabel: "Select documents report.pdf", depth: 1, folder: false, expanded: false, nameText: "report.pdf", sizeText: "2.1 MB", presenceText: "Verified", presenceStatus: "verified", checksumText: "5a2f8c10", notesText: "Evidence matches the recorded file." }) },
    { key: "baselined", parentKey: "folder", rowView: Object.freeze({ checked: false, mixed: false, selectionDisabled: false, selectionLabel: "Select documents draft.docx", depth: 1, folder: false, expanded: false, nameText: "draft.docx", sizeText: "412 KB", presenceText: "Baselined", presenceStatus: "baselined", checksumText: "90ef12ab", notesText: "Evidence was recorded for the first time." }) },
    { key: "verifying", rowView: Object.freeze({ checked: true, mixed: false, selectionDisabled: false, selectionLabel: "Select verifying.iso", depth: 0, folder: false, expanded: false, nameText: "verifying.iso", sizeText: "1.4 GB", presenceText: "Verifying", presenceStatus: "", lifecycleKey: "verifying", progressPercent: 67, checksumText: "—", notesText: "Projected integrity verification is in progress." }) },
    { key: "completed", rowView: Object.freeze({ checked: true, mixed: false, selectionDisabled: false, selectionLabel: "Select completed.iso", depth: 0, folder: false, expanded: false, nameText: "completed.iso", sizeText: "824 MB", presenceText: "Completed", presenceStatus: "", lifecycleKey: "completed", checksumText: "2468bdf1", notesText: "Projected integrity verification completed." }) },
    { key: "unverified", rowView: Object.freeze({ checked: false, mixed: false, selectionDisabled: false, selectionLabel: "Select todo.txt", depth: 0, folder: false, expanded: false, nameText: "todo.txt", sizeText: "2.8 KB", presenceText: "Unverified", presenceStatus: "unverified", checksumText: "—", notesText: "No verification evidence exists yet." }) },
    { key: "modified", rowView: Object.freeze({ checked: true, mixed: false, selectionDisabled: false, selectionLabel: "Select catalog.db", depth: 0, folder: false, expanded: false, nameText: "catalog.db", sizeText: "4.2 MB", presenceText: "Modified", presenceStatus: "modified", checksumText: "2468bdf1", notesText: "Recorded metadata is stale." }) },
    { key: "reappeared", rowView: Object.freeze({ checked: true, mixed: false, selectionDisabled: false, selectionLabel: "Select restored.log", depth: 0, folder: false, expanded: false, nameText: "restored.log", sizeText: "18 KB", presenceText: "Reappeared", presenceStatus: "reappeared", checksumText: "1357ace0", notesText: "Already projected as reappeared; underlying evidence is not inferred here." }) },
    { key: "unsupported", rowView: Object.freeze({ checked: false, mixed: false, selectionDisabled: true, selectionLabel: "Selection unavailable for device-link", depth: 0, folder: false, expanded: false, nameText: "device-link", sizeText: "—", presenceText: "Unsupported", presenceStatus: "unsupported", checksumText: "—", notesText: "Entry type cannot be verified." }) },
    { key: "canceled", rowView: Object.freeze({ checked: false, mixed: false, selectionDisabled: false, selectionLabel: "Select canceled.iso", depth: 0, folder: false, expanded: false, nameText: "canceled.iso", sizeText: "1.4 GB", presenceText: "Canceled", presenceStatus: "canceled", checksumText: "—", notesText: "Verification stopped before evidence was produced." }) },
    { key: "missing", rowView: Object.freeze({ checked: true, mixed: false, selectionDisabled: false, selectionLabel: "Select missing.csv", depth: 0, folder: false, expanded: false, nameText: "missing.csv", sizeText: "—", presenceText: "Missing", presenceStatus: "missing", checksumText: "—", notesText: "The recorded file was not found." }) },
    { key: "mismatched", rowView: Object.freeze({ checked: true, mixed: false, selectionDisabled: false, selectionLabel: "Select archive.zip", depth: 0, folder: false, expanded: false, nameText: "archive.zip", sizeText: "18.4 MB", presenceText: "Mismatched", presenceStatus: "mismatched", checksumText: "90ef12ab", notesText: "The verified hash differs." }) },
    { key: "error", rowView: Object.freeze({ checked: false, mixed: false, selectionDisabled: true, selectionLabel: "Selection unavailable for locked.dat", depth: 0, folder: false, expanded: false, nameText: "locked.dat", sizeText: "—", presenceText: "Error", presenceStatus: "error", checksumText: "—", notesText: "Read failed." }) },
  ]);
  const LIFECYCLE_PROGRESS_CASES = Object.freeze([
    { key: "running", lifecycle: "executing", hue: "accent", frozen: false },
    { key: "resumed", lifecycle: "executing", hue: "accent", frozen: false },
    { key: "paused", lifecycle: "paused", hue: "yellow", frozen: true },
    { key: "canceled", lifecycle: "canceled", hue: "neutral", frozen: true },
  ]);
  const CONTROL_CASES = Object.freeze([
    { key: "button", className: "nami-button", tag: "button" },
    { key: "button_primary", className: "nami-button nami-button--primary", tag: "button" },
    { key: "button_clear", className: "nami-button nami-button--clear", tag: "button" },
    { key: "dropdown", className: "nami-combobox__trigger", tag: "button" },
    { key: "tri_state_checkbox", className: "nami-checkbox", tag: "input" },
    { key: "progress_determinate", className: "nami-progress", tag: "progress" },
    { key: "progress_indeterminate", className: "nami-progress", tag: "progress" },
    { key: "text_input", className: "nami-input", tag: "input" },
    { key: "toggle", className: "nami-toggle__control", tag: "input", checked: true },
    { key: "toggle_off", className: "nami-toggle__control", tag: "input", checked: false },
    { key: "chip", className: "nami-chip", tag: "button" },
    { key: "filter_copy", className: "nami-chip", tag: "button",
      operation: "copy", pressed: false },
    { key: "filter_copy_active", className: "nami-chip", tag: "button",
      operation: "copy", pressed: true },
    { key: "filter_delete", className: "nami-chip", tag: "button",
      operation: "delete", pressed: false },
    { key: "filter_delete_active", className: "nami-chip", tag: "button",
      operation: "delete", pressed: true },
    { key: "list_row", className: "nami-list-row", tag: "div" },
    { key: "tree_row", className: "nami-tree-row", tag: "div" },
    { key: "card", className: "nami-card", tag: "section" },
    { key: "task_card", className: "nami-task-card", tag: "button" },
    { key: "task_card_selected", className: "nami-task-card", tag: "button" },
    { key: "task_card_current", className: "nami-task-card", tag: "button" },
    { key: "dialog", className: "nami-dialog", tag: "dialog" },
    { key: "context_menu", className: "nami-menu__item", tag: "button" },
    { key: "segmented_control", className: "nami-segmented__item", tag: "button" },
  ]);
  const CONTROL_STATES = Object.freeze([
    { key: "rest" },
    { key: "hover" },
    { key: "pressed" },
    { key: "disabled" },
    { key: "focused" },
  ]);

  const [{
    dispatchInteractive,
    readCosmeticSection,
    replaceCosmeticSection,
  }, { renderText }, iconModule, { renderPlanRow }, { renderIntegrityRow }, { createTaskRail }, { createExecutionConfirmation }, { createPlanReviewPanel }, { createInventoryReviewPanel }] = await Promise.all([
    import("/bridge.js"),
    import("/render.js"),
    import("/icons.js"),
    import("/plan.js"),
    import("/integrity.js"),
    import("/rail.js"),
    import("/execution_confirmation.js"),
    import("/plan_review.js"),
    import("/inventory_review.js"),
  ]);
  const { createIcon, ICON_NAMES } = iconModule;
  if (
    typeof createIcon !== "function"
    || !Array.isArray(ICON_NAMES)
    || typeof renderPlanRow !== "function"
    || typeof renderIntegrityRow !== "function"
    || typeof createPlanReviewPanel !== "function"
  ) {
    throw new TypeError("installed icon registry has an invalid public shape");
  }
  galleryWatchdog = setTimeout(async () => {
    if (gallerySettled) return;
    gallerySettled = true;
    try {
      await dispatchInteractive(
        "test_report",
        Object.freeze({
          phase: "failure",
          failure: buildFailureEvidence(
            galleryStage, "Error", galleryMeasurementStep, "watchdog_timeout",
          ),
        }),
        validAccepted,
      );
    } catch {
      // The outer 75-second scenario deadline remains authoritative.
    }
  }, 60000);
  galleryStage = "page_setup";

  const forced = matchMedia("(forced-colors: active)").matches;
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const dark = matchMedia("(prefers-color-scheme: dark)").matches;
  const mode = forced ? "forced" : reduced ? "reduced" : dark ? "dark" : "light";
  const expectedTheme = dark ? "dark" : "light";
  const alternateTheme = expectedTheme === "dark" ? "light" : "dark";
  const initialCosmetic = await readCosmeticSection();
  if (initialCosmetic.value.theme !== expectedTheme) {
    throw new Error("the gallery cosmetic seed is unavailable");
  }
  await waitForTheme(expectedTheme);
  document.querySelector(".nami-task-rail__settings").click();
  const themeSelector = document.querySelector("#theme-mode");
  const themeTrigger = themeSelector?.querySelector(".nami-combobox__trigger");
  const alternateOption = document.querySelector(
    `.nami-combobox__option[data-value="${alternateTheme}"]`,
  );
  const expectedOption = document.querySelector(
    `.nami-combobox__option[data-value="${expectedTheme}"]`,
  );
  if (
    !(themeSelector instanceof HTMLElement)
    || !(themeTrigger instanceof HTMLButtonElement)
    || !(alternateOption instanceof HTMLElement)
    || !(expectedOption instanceof HTMLElement)
  ) {
    throw new Error("the product theme selector is unavailable");
  }
  await waitForThemeSelector(themeSelector, expectedTheme, false);
  themeTrigger.click();
  alternateOption.click();
  const changeImmediateValue = themeSelector.dataset.value;
  const changeImmediateDisabled = themeTrigger.disabled;
  if (
    changeImmediateValue !== expectedTheme
    || changeImmediateDisabled !== true
  ) {
    throw new Error("the selector rendered an unaccepted theme choice");
  }
  await waitForThemeSelector(themeSelector, alternateTheme, false);
  await waitForTheme(alternateTheme);
  const afterChange = await readCosmeticSection();
  if (
    afterChange.revision !== initialCosmetic.revision + 1
    || afterChange.value.theme !== alternateTheme
  ) {
    throw new Error("the selector change did not become authoritative");
  }

  themeTrigger.click();
  expectedOption.click();
  const restoreImmediateValue = themeSelector.dataset.value;
  const restoreImmediateDisabled = themeTrigger.disabled;
  if (
    restoreImmediateValue !== alternateTheme
    || restoreImmediateDisabled !== true
  ) {
    throw new Error("the selector rendered an unaccepted restore choice");
  }
  await waitForThemeSelector(themeSelector, expectedTheme, false);
  await waitForTheme(expectedTheme);
  const restoredCosmetic = await readCosmeticSection();
  if (
    restoredCosmetic.revision !== afterChange.revision + 1
    || restoredCosmetic.value.theme !== expectedTheme
  ) {
    throw new Error("the selector did not restore authoritative state");
  }
  const cosmeticReplacement = await replaceCosmeticSection(
    restoredCosmetic.revision,
    expectedTheme,
  );
  if (
    cosmeticReplacement.disposition !== "noop"
    || cosmeticReplacement.revision !== restoredCosmetic.revision
  ) {
    throw new Error("the gallery cosmetic replacement did not reconcile");
  }
  const finalCosmetic = await readCosmeticSection();
  await waitForTheme(expectedTheme);
  const cosmeticEvidence = Object.freeze({
    initial: initialCosmetic,
    after_change: afterChange,
    replacement: cosmeticReplacement,
    final: finalCosmetic,
    page_theme: document.documentElement.dataset.theme,
    selector: Object.freeze({
      initial_value: initialCosmetic.value.theme,
      initial_disabled: false,
      change_immediate_value: changeImmediateValue,
      change_immediate_disabled: changeImmediateDisabled,
      change_settled_value: afterChange.value.theme,
      change_settled_disabled: false,
      restore_immediate_value: restoreImmediateValue,
      restore_immediate_disabled: restoreImmediateDisabled,
      final_value: themeSelector.dataset.value,
      final_disabled: themeTrigger.disabled,
    }),
  });
  document.documentElement.dataset.testGalleryMarker = TEST_ONLY_GALLERY_MARKER;

  const app = document.querySelector("#app");
  const themeField = themeSelector.parentElement;
  if (!(app instanceof HTMLElement) || !(themeField instanceof HTMLElement)) {
    throw new TypeError("installed page app root is unavailable");
  }
  app.replaceChildren();
  // The specimen gallery is a document, not a viewport-bounded task page.
  app.style.blockSize = "auto";
  app.style.gridTemplateRows = "none";
  app.style.overflow = "visible";
  const galleryHeader = document.createElement("header");
  galleryHeader.className = "nami-shell__header";
  const heading = document.createElement("h1");
  renderText(heading, "NamiSync component gallery");
  const status = document.createElement("p");
  status.id = "host-status";
  status.setAttribute("role", "status");
  renderText(status, `Gallery ${mode} measuring`);
  galleryHeader.append(heading, status, themeField);
  app.append(galleryHeader);

  // The gallery replaces the task page; its preview has no execution callback.
  document.querySelector("#execution-confirmation")?.remove();
  const confirmationPreview = createExecutionConfirmation([
    app, document.querySelector("#theme-options"),
  ]);
  document.body.append(confirmationPreview.element);
  const previewButton = document.createElement("button");
  previewButton.type = "button";
  previewButton.className = "nami-button nami-button--secondary";
  previewButton.dataset.galleryConfirmationPreview = "";
  renderText(previewButton, "Preview destructive confirmation");
  const previewResult = document.createElement("span");
  previewResult.setAttribute("role", "status");
  renderText(previewResult, "Preview only. No files will change.");
  previewButton.addEventListener("click", () => {
    confirmationPreview.show({
      destructiveOperationCount: 13,
      returnFocus: previewButton,
      onCancel: () => renderText(previewResult, "Preview canceled. No files were changed."),
      onConfirm: () => renderText(previewResult, "Preview confirmed. No files were changed."),
    });
  });
  galleryHeader.append(previewButton, previewResult);

  const galleryRail = createTaskRail({
    onCreate() {},
    onSelect() {},
    onClose() {},
    onRetryUpdates() {},
    onSettings() {},
  });
  galleryRail.render([
    {
      taskId: "task-gallery-executing", label: "Current sync", review: null,
      sessionId: "1".repeat(32),
      form: { source: { text: "C:\\source" }, target: { text: "D:\\target" } },
      sessionState: "active", executionStarted: true, executionControlState: "running",
      snapshot: { session_id: "1".repeat(32), session_state: "active", phase: "sync", presentation: {
        value: 40, determinate: true, indeterminate: false,
        items_done: 4, items_total: 10,
        throughput_bytes_per_second: null, eta_seconds: null,
      } },
      error: null, closePending: false, executionAttempt: null,
    },
    {
      taskId: "task-gallery-paused", label: "Paused verification", review: null,
      sessionId: "2".repeat(32),
      form: { source: { text: "C:\\source" }, target: { text: "D:\\target" } },
      sessionState: "active", executionStarted: true, executionControlState: "paused",
      snapshot: { session_id: "2".repeat(32), session_state: "active", phase: "verify", presentation: {
        value: 70, determinate: true, indeterminate: false,
        items_done: 7, items_total: 10,
        throughput_bytes_per_second: null, eta_seconds: null,
      } },
      error: null, closePending: false, executionAttempt: null,
    },
    {
      taskId: "task-gallery-canceled", label: "Canceled sync", review: null,
      form: { source: { text: "C:\\source" }, target: { text: "D:\\target" } },
      sessionState: "canceled", executionStarted: true, executionControlState: "running",
      snapshot: null, error: null, closePending: false, executionAttempt: null,
    },
  ], "task-gallery-executing", false);
  galleryRail.element.querySelector('.nami-task-card[aria-current="page"]')
    ?.setAttribute("aria-selected", "true");
  app.append(galleryRail.element);

  function icon(name, size = "md") {
    const value = createIcon(document, name, size);
    if (!(value instanceof HTMLElement)) {
      throw new TypeError("icon registry did not create an element");
    }
    value.setAttribute("aria-hidden", "true");
    return value;
  }

  function resolvedStateAliases(element) {
    const probe = document.createElement("span");
    probe.style.color = "var(--nami-state-foreground)";
    probe.style.backgroundColor = "var(--nami-state-background)";
    probe.style.borderColor = "var(--nami-state-indicator)";
    probe.style.forcedColorAdjust = "none";
    probe.style.position = "fixed";
    probe.style.visibility = "hidden";
    element.append(probe);
    const style = getComputedStyle(probe);
    const value = {
      foreground: style.color,
      background: style.backgroundColor,
      indicator: style.borderColor,
    };
    probe.remove();
    return value;
  }

  function computedRow(element, definition, shape, text) {
    const style = getComputedStyle(element);
    const aliases = resolvedStateAliases(element);
    const fontSize = parseFloat(style.fontSize);
    const fontWeight = parseInt(style.fontWeight, 10) || 400;
    const shapeStyle = getComputedStyle(shape, "::before");
    const shapeBounds = shape.getBoundingClientRect();
    return {
      key: definition.key,
      text: definition.text,
      hue: definition.hue,
      form: definition.form,
      rendered_form: transparentColor(style.backgroundColor) ? "text" : "fill",
      icon: definition.icon,
      shape: definition.shape,
      cue: definition.cue,
      visible_text: text.textContent,
      shape_content: shapeStyle.content,
      shape_color: shapeStyle.color,
      shape_display: shapeStyle.display,
      shape_visibility: shapeStyle.visibility,
      shape_opacity: shapeStyle.opacity,
      shape_width: shapeBounds.width,
      shape_height: shapeBounds.height,
      height: element.getBoundingClientRect().height,
      foreground: style.color,
      background: style.backgroundColor,
      indicator: shapeStyle.color,
      border_width: style.borderWidth,
      border_style: style.borderStyle,
      alias_foreground: aliases.foreground,
      alias_background: aliases.background,
      alias_indicator: aliases.indicator,
      aliases_consumed: style.color === aliases.foreground &&
        style.backgroundColor === aliases.background &&
        shapeStyle.color === aliases.indicator,
      large_text: fontSize >= 24 || (fontSize >= 18.66 && fontWeight >= 700),
      icon_color: getComputedStyle(element.querySelector(".nami-icon")).backgroundColor,
      mask_image: getComputedStyle(element.querySelector(".nami-icon")).maskImage,
    };
  }

  function semanticRows(definitions, prefix, className) {
    const section = document.createElement("section");
    section.dataset.gallerySection = prefix;
    const specimens = [];
    for (const definition of definitions) {
      const row = document.createElement("div");
      row.className = className;
      row.dataset[prefix] = definition.key;
      row.dataset.form = definition.form;
      row.dataset.shape = definition.shape;
      const glyph = icon(definition.icon);
      const shape = document.createElement("span");
      shape.className = "nami-state-cue";
      shape.setAttribute("aria-hidden", "true");
      const text = document.createElement("span");
      renderText(text, `${definition.text}: ${definition.cue}`);
      row.append(glyph, shape, text);
      section.append(row);
      specimens.push({ row, definition, shape, text });
    }
    app.append(section);
    return specimens.map(({ row, definition, shape, text }) =>
      computedRow(row, definition, shape, text),
    );
  }

  function transparentColor(value) {
    const normalized = value.toLowerCase().replaceAll(" ", "");
    return normalized === "transparent"
      || /^rgba\([^)]*,0(?:\.0+)?\)$/u.test(normalized)
      || /\/0(?:\.0+)?%?\)$/u.test(normalized);
  }

  function lifecycleProgressRows(definitions) {
    const section = document.createElement("section");
    section.dataset.gallerySection = "lifecycle_progress";
    const specimens = [];
    for (const definition of definitions) {
      const specimen = document.createElement("div");
      specimen.dataset.galleryLifecycleProgress = definition.key;
      const label = document.createElement("span");
      renderText(label, definition.key);
      const progress = document.createElement("div");
      progress.className = "nami-progress";
      progress.dataset.lifecycle = definition.lifecycle;
      progress.setAttribute("role", "progressbar");
      progress.setAttribute("aria-label", `${definition.key} progress`);
      progress.setAttribute("aria-valuemin", "0");
      progress.setAttribute("aria-valuemax", "100");
      progress.setAttribute("aria-valuenow", "55");
      const bar = document.createElement("div");
      bar.className = "nami-progress__bar";
      bar.style.setProperty("--nami-progress-value", "55%");
      progress.append(bar);
      const motionProbe = document.createElement("div");
      motionProbe.className = "nami-progress nami-progress--indeterminate";
      motionProbe.dataset.lifecycle = definition.lifecycle;
      motionProbe.style.position = "fixed";
      motionProbe.style.visibility = "hidden";
      const motionBar = document.createElement("div");
      motionBar.className = "nami-progress__bar";
      motionProbe.append(motionBar);
      specimen.append(label, progress, motionProbe);
      section.append(specimen);
      specimens.push({ definition, progress, bar, motionBar });
    }
    app.append(section);
    return specimens;
  }

  function controlElement(definition, state) {
    let root = document.createElement(definition.tag);
    let element = root;
    element.className = definition.className;
    if (definition.operation !== undefined) {
      element.dataset.operation = definition.operation;
    }
    if (definition.key === "button_clear") {
      element.append(icon("dismiss", "sm"));
      const text = document.createElement("span");
      renderText(text, "Clear");
      element.append(text);
    } else if (definition.key === "dropdown") {
      root = document.createElement("div");
      root.className = "nami-combobox";
      element = document.createElement("button");
      element.className = definition.className;
      element.type = "button";
      element.setAttribute("role", "combobox");
      element.setAttribute("aria-haspopup", "listbox");
      element.setAttribute("aria-expanded", "false");
      const value = document.createElement("span");
      renderText(value, "Folder");
      element.append(value);
      root.append(element);
    } else if (definition.key === "tri_state_checkbox") {
      element.type = "checkbox";
      element.indeterminate = true;
      element.setAttribute("aria-checked", "mixed");
    } else if (definition.key === "progress_determinate") {
      root = document.createElement("div");
      root.className = "nami-progress";
      root.dataset.lifecycle = "executing";
      root.setAttribute("role", "progressbar");
      root.setAttribute("aria-valuemin", "0");
      root.setAttribute("aria-valuemax", "100");
      root.setAttribute("aria-valuenow", "55");
      const bar = document.createElement("div");
      bar.className = "nami-progress__bar";
      bar.style.setProperty("--nami-progress-value", "55%");
      root.append(bar);
      element = root;
    } else if (definition.key === "progress_indeterminate") {
      root = document.createElement("div");
      root.className = "nami-progress nami-progress--indeterminate";
      root.dataset.lifecycle = "executing";
      root.setAttribute("role", "progressbar");
      const bar = document.createElement("div");
      bar.className = "nami-progress__bar";
      root.append(bar);
      element = root;
    } else if (definition.key === "text_input") {
      element.type = "text";
      element.value = "NamiSync";
    } else if (definition.key === "toggle" || definition.key === "toggle_off") {
      root = document.createElement("label");
      root.className = "nami-toggle";
      element = document.createElement("input");
      element.className = "nami-toggle__control";
      element.type = "checkbox";
      element.setAttribute("role", "switch");
      element.checked = definition.checked;
      const toggleText = document.createElement("span");
      renderText(toggleText, "Mirror options");
      root.append(element, toggleText);
    } else if (definition.key === "list_row") {
      element.setAttribute("role", "option");
      element.setAttribute("aria-selected", "false");
      renderText(element, "List row");
    } else if (definition.key === "tree_row") {
      element.setAttribute("role", "treeitem");
      element.setAttribute("aria-selected", "false");
      renderText(element, "Tree row");
    } else if (definition.key.startsWith("task_card")) {
      if (definition.key === "task_card_selected") {
        element.setAttribute("aria-selected", "true");
      } else if (definition.key === "task_card_current") {
        element.setAttribute("aria-current", "true");
      }
      renderText(element, "Task card");
    } else if (definition.key === "dialog") {
      element.open = true;
      renderText(element, "Confirm operation");
    } else if (definition.key === "context_menu") {
      root = document.createElement("div");
      root.className = "nami-menu";
      root.setAttribute("role", "menu");
      element = document.createElement("button");
      element.className = "nami-menu__item";
      element.setAttribute("role", "menuitem");
      renderText(element, "Context action");
      root.append(element);
    } else if (definition.key === "segmented_control") {
      root = document.createElement("div");
      root.className = "nami-segmented";
      root.setAttribute("role", "radiogroup");
      root.setAttribute("aria-label", "Activity mode");
      const sync = document.createElement("button");
      sync.className = "nami-segmented__item";
      sync.setAttribute("role", "radio");
      sync.setAttribute("aria-checked", "true");
      renderText(sync, "Sync");
      const integrity = document.createElement("button");
      integrity.className = "nami-segmented__item";
      integrity.setAttribute("role", "radio");
      integrity.setAttribute("aria-checked", "false");
      renderText(integrity, "Integrity");
      root.append(sync, integrity);
      element = sync;
    } else if (definition.key !== "progress_indeterminate") {
      renderText(element, definition.key.replaceAll("_", " "));
    }
    if (definition.key === "button") {
      element.prepend(icon("info"));
    }
    element.dataset.galleryControl = definition.key;
    element.dataset.galleryState = state;
    element.setAttribute("aria-label", `${definition.key} ${state}`);
    if (
      element.tagName === "BUTTON"
      && !new Set(["dropdown", "segmented_control"]).has(definition.key)
    ) {
      element.setAttribute("aria-pressed", String(definition.pressed ?? false));
    }
    if (state === "disabled") {
      if ("disabled" in element) {
        element.disabled = true;
      }
      element.setAttribute("aria-disabled", "true");
      if (definition.key === "dropdown") {
        root.setAttribute("aria-disabled", "true");
      }
    }
    if (state === "focused") {
      element.tabIndex = 0;
    }
    return { root, target: element };
  }

  function durationMilliseconds(value) {
    return value.split(",").reduce((maximum, raw) => {
      const part = raw.trim();
      const amount = parseFloat(part) || 0;
      const milliseconds = part.endsWith("ms") ? amount : amount * 1000;
      return Math.max(maximum, milliseconds);
    }, 0);
  }

  galleryStage = "semantic_matrix";
  const lifecycles = semanticRows(
    LIFECYCLE_CASES,
    "lifecycle",
    "nami-status-pill",
  );
  const intents = semanticRows(INTENT_CASES, "intent", "nami-badge");
  const lifecycleProgressSpecimens = lifecycleProgressRows(
    LIFECYCLE_PROGRESS_CASES,
  );
  galleryStage = "plan_matrix";
  galleryMeasurementStep = "plan_list_construction";
  const planSection = document.createElement("section");
  planSection.className = "nami-card";
  planSection.dataset.gallerySection = "plan_rows";
  planSection.style.gridArea = "work";
  function createFileList(title, label, headers, definitions, renderer, caseName) {
    const heading = document.createElement("h2");
    renderText(heading, title);
    const list = document.createElement("div");
    list.className = `nami-file-list nami-table-scroll${caseName === "plan" ? " nami-plan-review" : ""}`;
    if (caseName === "plan") {
      list.style.display = "block";
      list.style.blockSize = "auto";
      list.style.gridTemplateRows = "none";
    }
    list.setAttribute("role", "table");
    list.setAttribute("aria-label", label);
    const grid = document.createElement("div");
    grid.className = `nami-file-list__grid nami-table-layout${caseName === "plan" ? " nami-file-list__grid--plan" : ""}`;
    const header = document.createElement("div");
    header.className = "nami-file-list__header nami-table__header";
    header.setAttribute("role", "row");
    const columnNames = headers.length === 7
      ? (caseName === "plan"
        ? ["selection", "name", "primary", "secondary", "size", "modified", "notes"]
        : ["selection", "name", "size", "primary", "secondary", "modified", "notes"])
      : ["selection", "name", "size", "primary", "secondary", "notes"];
    const rootFontSize = parseFloat(
      getComputedStyle(document.documentElement).fontSize,
    );
    if (!Number.isFinite(rootFontSize) || rootFontSize <= 0) {
      throw new TypeError("gallery root font size is unavailable");
    }
    const columnMinimums = [
      rootFontSize * 2,
      rootFontSize * 12,
      ...(caseName === "plan"
        ? [rootFontSize * 6, rootFontSize * 7, rootFontSize * 5]
        : [rootFontSize * 5, rootFontSize * 8, rootFontSize * 7]),
      ...(headers.length === 7 ? [rootFontSize * 7] : []),
      rootFontSize * 14,
    ];
    let masterCheckbox = null;
    for (const [index, text] of headers.entries()) {
      const cell = document.createElement("div");
      cell.className = "nami-file-list__header-cell";
      cell.setAttribute("role", "columnheader");
      if (index === 0) {
        cell.setAttribute("aria-label", "Selection");
        masterCheckbox = document.createElement("input");
        masterCheckbox.className = "nami-checkbox";
        masterCheckbox.type = "checkbox";
        masterCheckbox.setAttribute("aria-label", `Select all ${label} rows`);
        cell.append(masterCheckbox);
      } else {
        renderText(cell, text);
      }
      if (index < headers.length - 1) {
        const resizer = document.createElement("div");
        resizer.className = "nami-file-list__column-resizer";
        resizer.dataset.column = columnNames[index];
        resizer.dataset.columnIndex = String(index);
        resizer.dataset.minimum = String(columnMinimums[index]);
        resizer.setAttribute("role", "separator");
        resizer.setAttribute("aria-orientation", "vertical");
        resizer.setAttribute(
          "aria-label",
          `Resize ${text || "selection"} column`,
        );
        resizer.tabIndex = 0;
        cell.append(resizer);
      }
      header.append(cell);
    }
    const body = document.createElement("div");
    body.className = "nami-file-list__body nami-table__body";
    body.setAttribute("role", "rowgroup");
    for (const definition of definitions) {
      const row = document.createElement("div");
      const rowView = caseName === "plan"
        ? { ...definition.rowView, modifiedText: definition.rowView.modifiedText ?? "2026-09-17 12:34" }
        : definition.rowView;
      renderer(row, rowView);
      if (caseName === "plan") {
        row.insertBefore(row.querySelector(".nami-file-row__size"),
          row.querySelector(".nami-plan-row__modified"));
        if ([...row.children].map((cell) => cell.dataset.fileColumn).join(",")
            !== "selection,name,primary,secondary,size,secondary,notes") {
          throw new Error("Gallery Plan cells do not match their headers");
        }
      }
      row.dataset.galleryCase = definition.key;
      row.dataset.galleryList = caseName;
      if (definition.parentKey !== undefined) {
        row.dataset.galleryParent = definition.parentKey;
      }
      body.append(row);
    }
    if (!(masterCheckbox instanceof HTMLInputElement)) {
      throw new TypeError("gallery master selection control is unavailable");
    }
    const folderReconcilers = [];
    for (const folder of body.querySelectorAll('[data-folder="true"]')) {
      const disclosure = folder.querySelector(".nami-file-row__disclosure");
      const folderCheckbox = folder.querySelector(".nami-checkbox");
      const children = [...body.querySelectorAll(
        `[data-gallery-parent="${folder.dataset.galleryCase}"]`,
      )];
      const childCheckboxes = children.map((child) =>
        child.querySelector(".nami-checkbox")
      );
      if (
        !(disclosure instanceof HTMLButtonElement)
        || !(folderCheckbox instanceof HTMLInputElement)
        || children.length < 2
        || !childCheckboxes.every(
          (checkbox) => checkbox instanceof HTMLInputElement,
        )
      ) {
        throw new TypeError("gallery folder controls are unavailable");
      }
      const disclosureLabel = disclosure.ariaLabel.replace(
        /^(?:Collapse|Expand) /u,
        "",
      );
      disclosure.addEventListener("click", () => {
        const expanded = disclosure.ariaExpanded !== "true";
        disclosure.ariaExpanded = String(expanded);
        disclosure.ariaLabel = `${expanded ? "Collapse" : "Expand"} ${disclosureLabel}`;
        for (const child of children) {
          child.hidden = !expanded;
        }
      });
      const reconcileFolderCheckbox = () => {
        const selected = childCheckboxes.filter(
          (checkbox) => checkbox.checked,
        ).length;
        const all = selected === childCheckboxes.length;
        const mixed = selected > 0 && !all;
        folderCheckbox.checked = all;
        folderCheckbox.indeterminate = mixed;
        folderCheckbox.ariaChecked = mixed ? "mixed" : String(all);
      };
      folderReconcilers.push(reconcileFolderCheckbox);
      for (const checkbox of childCheckboxes) {
        checkbox.addEventListener("change", reconcileFolderCheckbox);
      }
      folderCheckbox.addEventListener("change", () => {
        for (const checkbox of childCheckboxes) {
          checkbox.checked = folderCheckbox.checked;
        }
        reconcileFolderCheckbox();
      });
    }
    const rowCheckboxes = [...body.querySelectorAll(
      '.nami-checkbox[type="checkbox"]',
    )];
    const selectableCheckboxes = rowCheckboxes.filter(
      (checkbox) => !checkbox.disabled,
    );
    const reconcileMasterCheckbox = () => {
      const all = selectableCheckboxes.every(
        (checkbox) => checkbox.checked && !checkbox.indeterminate,
      );
      const none = selectableCheckboxes.every(
        (checkbox) => !checkbox.checked && !checkbox.indeterminate,
      );
      masterCheckbox.checked = all;
      masterCheckbox.indeterminate = !all && !none;
      masterCheckbox.ariaChecked = masterCheckbox.indeterminate
        ? "mixed"
        : String(all);
    };
    body.addEventListener("change", reconcileMasterCheckbox);
    masterCheckbox.addEventListener("change", () => {
      for (const checkbox of selectableCheckboxes) {
        checkbox.checked = masterCheckbox.checked;
        checkbox.indeterminate = false;
        checkbox.ariaChecked = String(masterCheckbox.checked);
      }
      for (const reconcile of folderReconcilers) {
        reconcile();
      }
      reconcileMasterCheckbox();
    });
    reconcileMasterCheckbox();
    grid.append(header, body);
    list.append(grid);
    planSection.append(heading, list);
    const headerCells = [...header.children];
    const resizers = [...header.querySelectorAll(
      ".nami-file-list__column-resizer",
    )];
    const resizeState = {
      frozen: false,
      widths: null,
    };
    const applyFrozenLayout = () => {
      if (!resizeState.frozen || !Array.isArray(resizeState.widths)) {
        return;
      }
      const widths = resizeState.widths;
      grid.style.cssText = [
        `--nami-file-column-selection: ${widths[0].toFixed(3)}px`,
        "--nami-file-column-name: minmax(12rem, 1fr)",
        `--nami-file-column-size: ${widths[caseName === "plan" ? 4 : 2].toFixed(3)}px`,
        `--nami-file-column-primary: ${widths[caseName === "plan" ? 2 : 3].toFixed(3)}px`,
        `--nami-file-column-secondary: ${widths[caseName === "plan" ? 3 : 4].toFixed(3)}px`,
        ...(headerCells.length === 7
          ? [`--nami-file-column-modified: ${widths[5].toFixed(3)}px`]
          : []),
        ...(headerCells.length === 7
          ? [`--nami-file-column-notes: ${widths[6].toFixed(3)}px`]
          : [`--nami-file-column-notes: ${widths[5].toFixed(3)}px`]),
      ].join("; ");
      grid.dataset.columnsFrozen = "true";
    };
    const refreshResizerValues = () => {
      const notesIndex = headerCells.length - 1;
      const notesWidth = resizeState.frozen
        ? resizeState.widths[notesIndex]
        : headerCells[notesIndex].getBoundingClientRect().width;
      for (const resizer of resizers) {
        const index = Number(resizer.dataset.columnIndex);
        const current = headerCells[index].getBoundingClientRect().width;
        const maximum = current + Math.max(
          0,
          notesWidth - columnMinimums[headerCells.length - 1],
        );
        resizer.setAttribute(
          "aria-valuemin",
          String(Math.round(columnMinimums[index])),
        );
        resizer.setAttribute("aria-valuemax", String(Math.round(maximum)));
        resizer.setAttribute("aria-valuenow", String(Math.round(current)));
      }
    };
    const ensureFrozen = () => {
      if (resizeState.frozen) {
        return;
      }
      resizeState.widths = headerCells.map(
        (cell) => cell.getBoundingClientRect().width,
      );
      resizeState.frozen = true;
      applyFrozenLayout();
      refreshResizerValues();
    };
    const resizeFromSnapshot = (
      index,
      requestedDelta,
      startWidths,
      startNameWidth,
    ) => {
      const minimumDelta = index === 1
        ? columnMinimums[1] - startNameWidth
        : columnMinimums[index] - startWidths[index];
      const notesIndex = headerCells.length - 1;
      const maximumDelta = startWidths[notesIndex] - columnMinimums[notesIndex];
      const delta = Math.max(
        minimumDelta,
        Math.min(maximumDelta, requestedDelta),
      );
      const nextWidths = [...startWidths];
      if (index !== 1) {
        nextWidths[index] = startWidths[index] + delta;
      }
      nextWidths[notesIndex] = startWidths[notesIndex] - delta;
      resizeState.widths = nextWidths;
      applyFrozenLayout();
      refreshResizerValues();
      return delta;
    };
    for (const resizer of resizers) {
      const index = Number(resizer.dataset.columnIndex);
      if (!Number.isInteger(index) || index < 0 || index >= headerCells.length - 1) {
        throw new TypeError("gallery column resizer is invalid");
      }
      resizer.addEventListener("pointerdown", (event) => {
        event.preventDefault();
        ensureFrozen();
        const startX = event.clientX;
        const startWidths = [...resizeState.widths];
        const startNameWidth = headerCells[1].getBoundingClientRect().width;
        const move = (moveEvent) => resizeFromSnapshot(
          index,
          moveEvent.clientX - startX,
          startWidths,
          startNameWidth,
        );
        const finish = () => {
          window.removeEventListener("pointermove", move);
          window.removeEventListener("pointerup", finish);
        };
        window.addEventListener("pointermove", move);
        window.addEventListener("pointerup", finish, { once: true });
      });
      resizer.addEventListener("keydown", (event) => {
        if (!new Set(["ArrowLeft", "ArrowRight"]).has(event.key)) {
          return;
        }
        event.preventDefault();
        ensureFrozen();
        const direction = event.key === "ArrowRight" ? 1 : -1;
        resizeFromSnapshot(
          index,
          direction * 8,
          [...resizeState.widths],
          headerCells[1].getBoundingClientRect().width,
        );
      });
    }
    return {
      list,
      grid,
      header,
      body,
      masterCheckbox,
      refreshResizerValues,
    };
  }

  const planSpecimen = createFileList(
    "Projected sync plan rows",
    "Projected sync plan specimen",
    ["", "Name", "Action", "Checksum", "Size", "Modified", "Notes"],
    PLAN_ROW_CASES,
    renderPlanRow,
    "plan",
  );
  const integritySpecimen = createFileList(
    "Projected integrity rows",
    "Projected integrity specimen",
    ["", "Filename", "Size", "Presence", "Checksum", "Notes"],
    INTEGRITY_ROW_CASES,
    renderIntegrityRow,
    "integrity",
  );
  app.append(planSection);
  planSpecimen.refreshResizerValues();
  integritySpecimen.refreshResizerValues();
  galleryMeasurementStep = "plan_review_construction";
  let renderedGalleryTask = null;
  let galleryWindowRequests = [];
  const planReviewCallbacks = Object.fromEntries([
    "onViewChange", "onWindow", "onSelect", "onScopeSelect", "onExecute", "onControl",
    "onPlanAgain", "onHighlight", "onHighlightedSelect", "onExecutionDetail",
    "onFollowOverride", "onNavigateCurrent", "onRevealMove",
  ].map((name) => [name, () => {}]));
  planReviewCallbacks.onWindow = (review, offset) => {
    galleryWindowRequests.push(offset);
    if (offset === null || renderedGalleryTask === null) return;
    review.window = {
      ...review.window,
      offset,
      rows: Array.from(
        { length: Math.min(64, Math.max(0, review.window.total - offset)) },
        (_, index) => galleryRow(offset + index),
      ),
    };
    planReviewPanel.render(renderedGalleryTask);
  };
  const planReviewPanel = createPlanReviewPanel(planReviewCallbacks);
  planReviewPanel.element.dataset.gallerySection = "plan_review_controls";
  planReviewPanel.element.style.blockSize = "480px";
  planReviewPanel.element.style.gridColumn = "1 / -1";
  app.append(planReviewPanel.element);
  const planReviewTask = {
    review: {
      summary: {
        source_path: "C:\\source",
        target_path: "D:\\target",
        selected_operation_count: 12,
        selectable_operation_count: 21,
        preflight_ready: true,
        preflight_refusal_count: 0,
        warning_count: 0,
        required_bytes: "5368709120",
        search_query: "",
        filters: ["update", "move_update"],
        filter_counts: {
          all: 21, copy: 4, mkdir: 1, move: 3, rename: 1, update: 2,
          move_update: 1, trash: 2, delete: 1, noop: 2, error: 0,
          unsupported: 1, blocked: 2, notice: 1,
        },
        sort_column: "path", sort_direction: "ascending",
        selection_state: "reviewing", scope_selectable_operation_count: 21,
        scope_selected_operation_count: 12,
      },
      window: {
        disposition: "current", view_revision: 0, highlight_revision: 0,
        offset: 0, total: 0, rows: [],
        execution: {
          execution_revision: 0, session_id: null, result: null,
          started_at: null, ended_at: null,
          failed_operation_count: null, disk_capacity_failure_count: null,
          gap: null, trash_location: null,
        },
      },
      pending: null,
      message: "",
    },
    error: null,
    canPlanAgain: true,
    executionStarted: false,
    sessionState: "completed",
    executionControlState: "running",
    closePending: false,
    executionAttempt: null,
    form: { options: { verify_after_execute: true, deletion_policy: "trash" } },
  };
  galleryMeasurementStep = "plan_review_initial_render";
  const galleryMovePath = "projects\\archive\\a-long-relative-destination-that-remains-available-in-the-tooltip";
  const galleryMoveDisplay = `…\\${galleryMovePath.split("\\").at(-1)}`;
  planReviewTask.review.window.total = 1;
  planReviewTask.review.window.rows = [{
    node_id: `node-${"8".repeat(32)}`, display: `12 items moved to ${galleryMoveDisplay}`,
    depth: 0, is_container: true, visible_index: 0, parent_visible_index: null,
    first_child_visible_index: null, position_in_set: 1, set_size: 1,
    expanded: false, row_kind: "prior-group", operation_id: null, operation_kind: null,
    presentation_kind: null, prior_name: null,
    reason: null, blocked_reason: null, selection: "disabled", highlighted: false,
    selectable_operation_count: 0, selected_operation_count: 0, operation_count: 0,
    size: null, mtime_ns: null, dependency_count: 0, risk: "none",
    move_peer_id: `node-${"9".repeat(32)}`,
    move_group: { count: 12, destination_display: galleryMoveDisplay },
    notice: null, selection_exclusion_reason: null, execution: null,
  }];
  planReviewPanel.render(planReviewTask);
  const galleryMovePill = planReviewPanel.element.querySelector(".nami-plan-move-pill");
  const galleryMoveBadgeStyle = getComputedStyle(galleryMovePill.querySelector(".nami-badge"));
  const galleryDark = document.documentElement.dataset.theme === "dark";
  const galleryForced = matchMedia("(forced-colors: active)").matches;
  if (!galleryForced && (galleryMoveBadgeStyle.backgroundColor !== (galleryDark ? "rgb(51, 17, 85)" : "rgb(187, 136, 238)")
      || galleryMoveBadgeStyle.color !== (galleryDark ? "rgb(187, 136, 238)" : "rgb(51, 17, 85)"))
      || galleryMovePill.title !== `12 items moved to ${galleryMoveDisplay}`
      || galleryMovePill.ariaLabel !== galleryMovePill.title
      || getComputedStyle(galleryMovePill.querySelector(".nami-plan-move-pill__destination")).textOverflow !== "ellipsis") {
    throw new Error("move pill color, cap or accessible destination changed");
  }
  const planDetailsToggle = planReviewPanel.element.querySelector('[data-action="toggle-execution-details"]');
  const planItemPane = planReviewPanel.element.querySelector(".nami-plan-review__detail");
  planDetailsToggle.click();
  if (planDetailsToggle.ariaExpanded !== "true"
      || planItemPane.closest("[hidden]") !== null
      || !planItemPane.textContent.includes("Highlight an item to see its details.")) {
    throw new Error("Plan status card must show the empty item pane when expanded");
  }
  planDetailsToggle.click();
  galleryMeasurementStep = "plan_review_static_contract";
  const semanticSettings = planReviewPanel.element.querySelector(".nami-plan-review__settings");
  const filterSpecimen = planReviewPanel.element.querySelector('[data-filter="noop"]');
  galleryMeasurementStep = "plan_review_filter_spacing";
  if (filterSpecimen.children[1].textContent !== "No change"
      || filterSpecimen.children[2].textContent !== "2"
      || getComputedStyle(filterSpecimen).wordSpacing !== "0px") {
    throw new Error("filter label/count spacing must not stretch words");
  }
  const pathValues = [...planReviewPanel.element.querySelectorAll(".nami-labeled-path__value")];
  galleryMeasurementStep = "plan_review_path_alignment";
  if (Math.abs(pathValues[0].getBoundingClientRect().left - pathValues[1].getBoundingClientRect().left) > 0.5) {
    throw new Error("Plan path starts must align");
  }
  const resetBounds = planReviewPanel.element.querySelector('[data-action="plan-again"]').getBoundingClientRect();
  galleryMeasurementStep = "plan_review_reset_geometry";
  if (Math.abs(resetBounds.width - resetBounds.height) > 0.5) throw new Error("Plan again must be square");
  const semanticPaths = planReviewPanel.element.querySelector(".nami-plan-review__paths");
  const settingBounds = semanticSettings.getBoundingClientRect();
  const pathBounds = semanticPaths.getBoundingClientRect();
  const statusDetail = planReviewPanel.element.querySelector(".nami-plan-review__status-summary");
  const statusFeedback = planReviewPanel.element.querySelector(".nami-plan-review__status");
  galleryMeasurementStep = "plan_review_status_typography";
  if (getComputedStyle(statusFeedback).fontSize !== getComputedStyle(statusDetail).fontSize
      || getComputedStyle(statusFeedback).color !== getComputedStyle(statusDetail).color) {
    throw new Error("status feedback must share secondary status typography and color");
  }
  galleryMeasurementStep = "plan_review_caption_typography";
  if (getComputedStyle(semanticPaths).fontSize !== "12px"
      || getComputedStyle(semanticSettings).fontSize !== "12px") {
    throw new Error("Plan paths and semantic settings must use caption size");
  }
  galleryMeasurementStep = "plan_review_setting_alignment";
  if (Math.abs(settingBounds.left - resetBounds.left) > 4) {
    throw new Error("semantic icons must align optically with the Plan-again button");
  }
  galleryMeasurementStep = "plan_review_path_label_gap";
  for (const value of pathValues) {
    const label = value.previousElementSibling;
    if (value.getBoundingClientRect().left - label.getBoundingClientRect().right > 4.5) {
      throw new Error("path label gap must stay compact");
    }
  }
  const semanticColorProbe = document.createElement("span");
  semanticSettings.append(semanticColorProbe);
  galleryMeasurementStep = "plan_review_setting_states";
  for (const [verify, deletion, glyphs, tones] of [
    [true, "trash", ["arrow-sync-checkmark", "delete"], ["accent", "muted"]],
    [false, "additive", ["arrow-sync", "document-add"], ["muted", "accent"]],
  ]) {
    planReviewTask.form.options = { verify_after_execute: verify, deletion_policy: deletion };
    planReviewPanel.render(planReviewTask);
    const rows = [...semanticSettings.children].slice(0, 2);
    for (const [index, row] of rows.entries()) {
      const icon = row.querySelector(".nami-icon");
      const token = tones[index] === "accent" ? "--color-accent-fill" : "--color-neutral-foreground-secondary";
      semanticColorProbe.style.color = `var(${token})`;
      if (!icon.classList.contains(`nami-icon--${glyphs[index]}`)
          || getComputedStyle(icon).color !== getComputedStyle(semanticColorProbe).color
          || getComputedStyle(row.lastElementChild).color !== getComputedStyle(row).color) {
        throw new Error("semantic setting icon/label color mismatch");
      }
    }
    const currentSettings = semanticSettings.getBoundingClientRect();
    const currentPaths = semanticPaths.getBoundingClientRect();
    if (Math.abs(currentSettings.left - settingBounds.left) > 0.5
        || Math.abs(currentSettings.width - settingBounds.width) > 0.5
        || Math.abs(currentPaths.width - pathBounds.width) > 0.5) {
      throw new Error("semantic setting text shifted the path/setting slots");
    }
  }
  semanticColorProbe.style.color = "var(--color-neutral-foreground-tertiary)";
  const tertiaryColor = getComputedStyle(semanticColorProbe).color;
  for (const cell of app.querySelectorAll(".nami-file-row__size, .nami-plan-row__modified, .nami-file-row__notes")) {
    if (getComputedStyle(cell).color !== tertiaryColor) throw new Error("metadata must use tertiary text");
  }
  semanticColorProbe.remove();
  galleryMeasurementStep = "plan_review_session_states";
  planReviewPanel.render({ ...planReviewTask, review: null, sessionState: "active" });
  for (const action of ["execute", "plan-again", "pause", "cancel"]) {
    if (!planReviewPanel.element.querySelector(`[data-action="${action}"]`)?.disabled) {
      throw new Error(`loading Plan advertises unavailable ${action}`);
    }
  }
  if (!planReviewPanel.element.querySelector(".nami-plan-review__progress")
      .classList.contains("nami-progress--indeterminate")) {
    throw new Error("loading Plan status must show indeterminate planning");
  }
  planReviewPanel.render({ ...planReviewTask, review: null, sessionState: "failed", error: "Planning failed." });
  if (planReviewPanel.element.querySelector(".nami-plan-review__progress")
      .classList.contains("nami-progress--indeterminate")) {
    throw new Error("failed planning must stop indeterminate progress");
  }
  planReviewPanel.dispose();
  planReviewTask.form.options = { verify_after_execute: true, deletion_policy: "trash" };
  planReviewPanel.render(planReviewTask);
  if (planReviewPanel.element.querySelector('[data-action="execute"]').disabled) {
    throw new Error("loaded review must restore Execute after reuse");
  }
  if (planReviewPanel.element.querySelector(".nami-plan-review__progress")
      .classList.contains("nami-progress--indeterminate")) {
    throw new Error("ready Plan progress must return to idle");
  }
  galleryMeasurementStep = "plan_review_filter_menu";
  const filterTrigger = planReviewPanel.element.querySelector('[data-action="filter-menu"]');
  if (filterTrigger.children[2].textContent !== "2" || filterTrigger.dataset.active !== "true") {
    throw new Error("Filter trigger must count canonical categories");
  }
  filterTrigger.scrollIntoView({block: "center"});
  await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  filterTrigger.click();
  const menuCounts = [...planReviewPanel.element.querySelectorAll('.nami-filter-menu__popup:not([hidden]) .nami-filter-count')];
  if (menuCounts.length < 2 || menuCounts.some((count) =>
    Math.abs(count.getBoundingClientRect().right - menuCounts[0].getBoundingClientRect().right) > 0.5)) {
    throw new Error("filter menu counts must align right");
  }

  await new Promise(resolve => setTimeout(resolve, durationMilliseconds(getComputedStyle(filterTrigger).transitionDuration) + 30));
  const filterColorReference = document.createElement("span");
  filterColorReference.style.cssText = "position:fixed;visibility:hidden;forced-color-adjust:none";
  filterColorReference.style.backgroundColor = "var(--color-accent-fill)";
  filterColorReference.style.color = "var(--color-accent-fill-foreground)";
  app.append(filterColorReference);
  const activeFilterStyle = getComputedStyle(filterTrigger);
  const primaryFilterStyle = getComputedStyle(filterColorReference);
  const filterAccentPair = activeFilterStyle.backgroundColor === primaryFilterStyle.backgroundColor
    && activeFilterStyle.color === primaryFilterStyle.color;
  const activeFilterFill = activeFilterStyle.backgroundColor;
  const popup = planReviewPanel.element.querySelector(".nami-filter-menu__popup");
  const selectedFilter = popup.querySelector('[data-filter="update"]');
  selectedFilter.focus();
  planReviewTask.review.pending = "view";
  planReviewPanel.render(planReviewTask);
  if (popup.hidden || document.activeElement !== selectedFilter) throw new Error("pending filter focus lost");
  popup.dispatchEvent(new KeyboardEvent("keydown", {key: "Escape", bubbles: true}));
  if (!popup.hidden || document.activeElement !== filterTrigger) throw new Error("pending Escape focus lost");
  planReviewTask.review.pending = null;
  planReviewPanel.render(planReviewTask);
  const savedFilters = planReviewTask.review.summary.filters;
  planReviewTask.review.summary.filters = [];
  planReviewPanel.render(planReviewTask);
  if (filterTrigger.children[2].textContent !== "0" || filterTrigger.dataset.active !== "false") {
    throw new Error("inactive Filter counter must remain visible");
  }
  await new Promise(resolve => setTimeout(resolve, durationMilliseconds(getComputedStyle(filterTrigger).transitionDuration) + 30));
  filterColorReference.style.backgroundColor = "var(--color-button-fill)";
  filterColorReference.style.color = "var(--color-neutral-foreground)";
  const inactiveFilterStyle = getComputedStyle(filterTrigger);
  const neutralFilterStyle = getComputedStyle(filterColorReference);
  const filterNeutralPair = inactiveFilterStyle.backgroundColor === neutralFilterStyle.backgroundColor
    && inactiveFilterStyle.color === neutralFilterStyle.color;
  const inactiveFilterFill = inactiveFilterStyle.backgroundColor;
  filterColorReference.remove();
  planReviewTask.review.summary.filters = savedFilters;
  planReviewPanel.render(planReviewTask);

  const longDiagnostic = `literal terminal diagnostic ${"x".repeat(1600)}`;
  const longTrashLocation = `D:\\${"segment\\".repeat(4095)}file`;
  if (longTrashLocation.length !== 32767) throw new Error("trash-location fixture bound drifted");
  const calmExecutionResult = {
    headline: "success", filesystem: "succeeded", integrity: "not-run",
    recording: "ok", audit: "ok", disposition: "ran", canceled: false,
    phases: [], bytes_done: "0", bytes_total: "0", error: null,
    recording_degraded_items: 0, recording_issues: [],
    omitted_detail_count: 0, presentation_omitted_detail_count: 0,
    review_refusal: null,
  };
  const longExecutionResult = {
    ...calmExecutionResult,
    headline: "partial", filesystem: "failed", recording: "degraded",
    audit: "degraded",
    phases: [
      { phase: "prepare", status: "failed", error: longDiagnostic },
      { phase: "execute", status: "failed", error: longDiagnostic },
      { phase: "verify", status: "failed", error: longDiagnostic },
    ],
    error: longDiagnostic,
    recording_degraded_items: 1,
    recording_issues: [{ reason: "final-flush-failed", detail: longDiagnostic }],
  };
  const longExecutionDetail = {
    state: "current",
    operationId: "5".repeat(32),
    executionRevision: 1,
    focusNodeId: `node-${"7".repeat(32)}`,
    message: null,
    response: {
      disposition: "current", execution_revision: 1,
      operation_id: "5".repeat(32),
      operation: {
        kind: "copy", path: "C:\\source\\long-diagnostic.bin",
        result: "failed", reason: "io-error",
        detail: { diagnostic: longDiagnostic },
        recording: "degraded", recording_detail: longDiagnostic,
        detail_omitted_count: 0,
      },
      automatic_verification: null,
      evidence: { state: "unrecorded", content: null },
    },
  };

  const populatedRow = {
    node_id: `node-${"7".repeat(32)}`, display: "long-diagnostic.bin", depth: 0,
    is_container: false, visible_index: 0, parent_visible_index: null,
    first_child_visible_index: null, position_in_set: 1, set_size: 1000,
    expanded: false, row_kind: "operation", operation_id: "5".repeat(32),
    operation_kind: "copy", presentation_kind: "copy", prior_name: null, reason: null, blocked_reason: null,
    selection: "selected", selectable_operation_count: 1,
    selected_operation_count: 1, operation_count: 1, size: "4096",
    mtime_ns: "1000000000", dependency_count: 0, risk: "none",
    move_peer_id: null, move_group: null, notice: null, selection_exclusion_reason: null,
    execution: {
      operation: {
        result: "failed", reason: "io-error", recording: "degraded",
        recording_reason: "final-flush-failed", detail_omitted_count: 0,
      },
      automatic_verification: null,
      evidence: null,
    },
  };
  let galleryFocusedOperationId = null;


  function galleryRow(index) {
    const longOperation = index === 400;
    const identity = index.toString(16).padStart(32, "0");
    const selected = index < 12;
    return {
      ...populatedRow,
      node_id: longOperation ? populatedRow.node_id : "node-" + identity,
      operation_id: longOperation ? populatedRow.operation_id : identity,
      display: longOperation ? populatedRow.display : "operation-" + index + ".bin",
      visible_index: index,
      position_in_set: index + 1,
      selection: selected ? "selected" : "unselected",
      selected_operation_count: selected ? 1 : 0,
      highlighted: (longOperation ? populatedRow.operation_id : identity) === galleryFocusedOperationId,
      execution: longOperation ? populatedRow.execution : null,
    };
  }

  planReviewCallbacks.onHighlight = (review, gesture, nodeId) => {
    if (gesture !== "replace") throw new Error("gallery row activation changed");
    const row = review.window.rows.find((item) => item.node_id === nodeId);
    if (row?.operation_id !== populatedRow.operation_id) {
      throw new Error("gallery focus did not target the retained operation");
    }
    galleryFocusedOperationId = row.operation_id;
    review.summary.highlight_focus_node_id = row.node_id;
    review.summary.highlight_focus_visible_index = row.visible_index;
    review.summary.highlight_revision = (review.summary.highlight_revision ?? 0) + 1;
    for (const item of review.window.rows) item.highlighted = item.node_id === row.node_id;
    review.executionDetail = longExecutionDetail;
    planReviewPanel.render(renderedGalleryTask);
  };

  let diagnosticDefaultRailWidth = null;
  async function diagnosticLayout(caseName, blockSize, expanded, populated) {
    if (blockSize === null) planReviewPanel.element.style.removeProperty("block-size");
    else planReviewPanel.element.style.blockSize = `${blockSize}px`;
    const result = populated ? longExecutionResult : calmExecutionResult;
    galleryFocusedOperationId = null;
    galleryWindowRequests = [];
    renderedGalleryTask = {
      ...planReviewTask,
      executionStarted: true,
      sessionState: populated ? "failed" : "completed",
      review: {
        ...planReviewTask.review,
        summary: {
          ...planReviewTask.review.summary, selection_state: "committed",
          highlight_focus_node_id: null, highlight_focus_visible_index: null,
          highlight_revision: 0,
        },
        window: {
          ...planReviewTask.review.window,
          execution: {
            execution_revision: 1, session_id: "6".repeat(32), result,
            started_at: "2026-09-23T08:00:00+00:00",
            ended_at: "2026-09-23T08:00:04+00:00",
            failed_operation_count: populated ? 1 : 0,
            disk_capacity_failure_count: 0, gap: null,
            trash_location: populated ? longTrashLocation : null,
          },
          offset: 0,
          total: populated ? 1000 : 0,
          rows: populated ? [galleryRow(0)] : [],
        },
        executionDetail: null,
      },
    };
    planReviewPanel.render(renderedGalleryTask);
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const toggle = planReviewPanel.element.querySelector(".nami-plan-review__details-toggle");
    if (!(toggle instanceof HTMLButtonElement)) throw new TypeError(`${caseName} Details toggle is unavailable`);
    if ((toggle.getAttribute("aria-expanded") === "true") !== expanded && !toggle.hidden) toggle.click();
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const pageScroll = { x: window.scrollX, y: window.scrollY };
    planReviewPanel.element.scrollIntoView({ block: "end", inline: "nearest" });
    const content = planReviewPanel.element.querySelector(".nami-plan-review__content");
    const table = planReviewPanel.element.querySelector(".nami-plan-review__table-card");
    const tableHeader = table?.querySelector(".nami-file-list__header");
    const viewport = planReviewPanel.element.querySelector(".nami-plan-review__rows");
    const diagnostics = planReviewPanel.element.querySelector(".nami-plan-review__diagnostics");
    const globalDiagnostics = planReviewPanel.element.querySelector(".nami-plan-review__global-diagnostics");
    const issueRegion = planReviewPanel.element.querySelector(".nami-plan-review__execution-issues");
    const trashRegion = planReviewPanel.element.querySelector(".nami-plan-review__execution-trash");
    const detailRegion = planReviewPanel.element.querySelector(".nami-plan-review__detail");
    const detailBody = detailRegion.querySelector(".nami-plan-review__detail-body");
    if (!(content instanceof HTMLElement) || !(table instanceof HTMLElement)
        || !(tableHeader instanceof HTMLElement)
        || !(viewport instanceof HTMLElement) || !(diagnostics instanceof HTMLElement)
        || !(globalDiagnostics instanceof HTMLElement)
        || !(issueRegion instanceof HTMLElement) || !(trashRegion instanceof HTMLElement)
        || !(detailRegion instanceof HTMLElement) || !(detailBody instanceof HTMLElement)) {
      throw new TypeError(`${caseName} diagnostic geometry is unavailable`);
    }
    const initialOffset = renderedGalleryTask.review.window.offset;
    if (populated) {
      viewport.scrollTop = 400 * 24;
      viewport.dispatchEvent(new Event("scroll"));
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      await new Promise((resolve) => requestAnimationFrame(resolve));
    }
    const adoptedOffset = renderedGalleryTask.review.window.offset;
    let visibleRow = populated ? [...viewport.querySelectorAll("[data-node-id]")]
      .find((row) => Number(row.ariaRowIndex) === 402) : null;
    if (populated && visibleRow instanceof HTMLElement) {
      const focusedNodeId = visibleRow.dataset.nodeId;
      visibleRow.click();
      await new Promise((resolve) => requestAnimationFrame(resolve));
      visibleRow = [...viewport.querySelectorAll("[data-node-id]")]
        .find((row) => row.dataset.nodeId === focusedNodeId && row.isConnected) ?? null;
    }
    const rootBounds = planReviewPanel.element.getBoundingClientRect();
    const contentBounds = content.getBoundingClientRect();
    const tableBounds = table.getBoundingClientRect();
    const visibleColumns = diagnostics.hidden
      ? [] : [globalDiagnostics, detailRegion].filter((region) => !region.hidden);
    const visibleCount = expanded ? 2 : 0;
    const rootFits = planReviewPanel.element.scrollHeight <= planReviewPanel.element.clientHeight + 1
      && contentBounds.bottom <= rootBounds.bottom + 1;
    const tableUsable = tableBounds.height > 0 && viewport.clientHeight >= 24;
    function controlFits(control) {
      if (control.closest("[hidden]") !== null) return true;
      const bounds = control.getBoundingClientRect();
      return bounds.width > 0 && bounds.height > 0
        && bounds.left >= rootBounds.left - 1 && bounds.right <= rootBounds.right + 1;
    }
    const hiddenMenuControl = planReviewPanel.element.querySelector(
      ".nami-filter-menu__popup[hidden] button",
    );
    const hiddenDescendantExempt = hiddenMenuControl instanceof HTMLButtonElement
      && controlFits(hiddenMenuControl);
    const collapsedControl = document.createElement("button");
    collapsedControl.tabIndex = 0;
    collapsedControl.style.cssText = [
      "appearance: none", "position: absolute", "inline-size: 0", "block-size: 0",
      "min-inline-size: 0", "min-block-size: 0", "padding: 0", "border: 0",
      "margin: 0", "overflow: hidden",
    ].join(";");
    planReviewPanel.element.append(collapsedControl);
    const visibleCollapsedRejected = !controlFits(collapsedControl);
    collapsedControl.remove();
    const list = table.querySelector(".nami-plan-review__list");
    const viewportBounds = viewport.getBoundingClientRect();
    const listBounds = list.getBoundingClientRect();
    const rowBounds = visibleRow?.getBoundingClientRect();
    const wholeRowReachable = !populated || (
      rowBounds !== undefined
      && rowBounds.height >= 23.5
      && rowBounds.top >= Math.max(viewportBounds.top, listBounds.top, rootBounds.top) - 1
      && rowBounds.bottom <= Math.min(
        viewportBounds.bottom, listBounds.top + list.clientHeight, rootBounds.bottom,
      ) + 1
    );
    const otherControlsFit = [...planReviewPanel.element.querySelectorAll("button")]
      .filter((control) => !control.closest(".nami-plan-review__list"))
      .every(controlFits);
    function hitTableControl(control) {
      const bounds = control.getBoundingClientRect();
      const x = (bounds.left + bounds.right) / 2;
      const y = (bounds.top + bounds.bottom) / 2;
      const hit = document.elementFromPoint(x, y);
      return bounds.width > 0 && bounds.height > 0
        && bounds.left >= Math.max(listBounds.left, rootBounds.left) - 1
        && bounds.right <= Math.min(listBounds.left + list.clientWidth, rootBounds.right) + 1
        && y >= listBounds.top && y <= listBounds.top + list.clientHeight
        && (hit === control || control.contains(hit));
    }
    let rowActivationReachable = !populated;
    if (populated && visibleRow !== null) {
      const previousFocus = document.activeElement;
      const previousLeft = list.scrollLeft;
      const previousTop = viewport.scrollTop;
      list.scrollLeft = list.scrollWidth;
      await new Promise((resolve) => requestAnimationFrame(resolve));
      list.scrollLeft = 0;
      const rowVisibleBounds = visibleRow.getBoundingClientRect();
      const rowX = Math.max(listBounds.left, rowVisibleBounds.left) + 48;
      const rowY = (rowVisibleBounds.top + rowVisibleBounds.bottom) / 2;
      const rowHit = document.elementFromPoint(rowX, rowY);
      visibleRow.focus({ preventScroll: true });
      rowActivationReachable = wholeRowReachable
        && rowHit !== null && visibleRow.contains(rowHit)
        && document.activeElement === visibleRow
        && visibleRow.dataset.highlighted === "true";
      if (previousFocus instanceof HTMLElement) previousFocus.focus({ preventScroll: true });
      list.scrollLeft = previousLeft;
      viewport.scrollTop = previousTop;
    }
    const previousLeft = list.scrollLeft;
    const headerControls = [...list.querySelectorAll(".nami-file-list__header button")];
    const headerScrollObservations = [];
    const headersReachable = headerControls.map((control) => {
      const observation = () => {
        const rect = control.getBoundingClientRect();
        return [list.scrollLeft, rect.left, rect.right, listBounds.left,
          listBounds.left + list.clientWidth].map((value) => Number(value.toFixed(3)));
      };
      list.scrollLeft = 0;
      const start = observation();
      list.scrollLeft = list.scrollWidth;
      const end = observation();
      list.scrollLeft += control.getBoundingClientRect().left - listBounds.left;
      headerScrollObservations.push([...start, ...end, ...observation()]);
      return hitTableControl(control);
    }).every(Boolean);
    list.scrollLeft = previousLeft;
    const noHorizontalControlClipping = otherControlsFit && rowActivationReachable && headersReachable;
    const cardinalityExact = diagnostics.hidden === (visibleCount === 0)
      && visibleColumns.length === visibleCount
      && (visibleCount === 0 || visibleColumns[1].getBoundingClientRect().top
        >= visibleColumns[0].getBoundingClientRect().bottom - 1);
    const issuesContentComplete = !expanded || !populated || (
      issueRegion.textContent.includes(longDiagnostic)
    );
    const trashContentComplete = !expanded || !populated || (
      trashRegion.textContent === `Trash location: ${longTrashLocation}`
    );
    const detailContentComplete = !expanded || !populated || (
      detailRegion.textContent.includes(longDiagnostic)
    );
    issueRegion.scrollTop = issueRegion.scrollHeight;
    trashRegion.scrollTop = trashRegion.scrollHeight;
    detailRegion.scrollTop = detailRegion.scrollHeight;
    const endReachable = (region) => {
      for (let node = region; node instanceof HTMLElement
          && planReviewPanel.element.contains(node); node = node.parentElement) {
        if (node.scrollHeight <= node.clientHeight + 1) continue;
        const overflowY = getComputedStyle(node).overflowY;
        if (overflowY === "hidden" || overflowY === "clip") return false;
        if (!["auto", "scroll", "overlay"].includes(overflowY)) continue;
        const previous = node.scrollTop;
        node.scrollTop = node.scrollHeight;
        const reached = node.scrollTop > 0
          && node.scrollTop + node.clientHeight >= node.scrollHeight - 1;
        node.scrollTop = previous;
        return reached;
      }
      return region.scrollHeight <= region.clientHeight + 1
        && region.getBoundingClientRect().bottom <= rootBounds.bottom + 1;
    };
    const issuesContentReachable = issuesContentComplete && (!expanded || !populated || endReachable(issueRegion));
    const trashContentReachable = trashContentComplete && (!expanded || !populated || endReachable(trashRegion));
    const detailContentReachable = detailContentComplete && (!expanded || !populated || endReachable(detailRegion));
    issueRegion.focus();
    const issuesKeyboardReachable = !expanded || !populated || document.activeElement === issueRegion;
    trashRegion.focus();
    const trashKeyboardReachable = !expanded || !populated || document.activeElement === trashRegion;
    detailRegion.focus();
    const detailKeyboardReachable = !expanded || !populated || document.activeElement === detailRegion;
    const lineHeight = parseFloat(getComputedStyle(detailBody).lineHeight);
    const readableBody = !expanded || !populated || detailRegion.clientHeight >= Math.max(48, lineHeight * 3);
    toggle.focus();
    const disclosureBounds = toggle.getBoundingClientRect();
    const summary = planReviewPanel.element.querySelector(".nami-plan-review__summary");
    function disclosureFitsRegion(region) {
      if (!(region instanceof HTMLElement)) return false;
      const bounds = region.getBoundingClientRect();
      const left = bounds.left + region.clientLeft;
      const top = bounds.top + region.clientTop;
      return disclosureBounds.left >= left - 1
        && disclosureBounds.right <= left + region.clientWidth + 1
        && disclosureBounds.top >= top - 1
        && disclosureBounds.bottom <= top + region.clientHeight + 1;
    }
    const disclosureHit = document.elementFromPoint(
      (disclosureBounds.left + disclosureBounds.right) / 2,
      (disclosureBounds.top + disclosureBounds.bottom) / 2,
    );
    const disclosureReachable = document.activeElement === toggle
      && disclosureBounds.width > 0 && disclosureBounds.height > 0
      && [planReviewPanel.element, summary].every(disclosureFitsRegion)
      && (disclosureHit === toggle || toggle.contains(disclosureHit));
    const placeholderPresent = !expanded || populated || (
      !detailRegion.hidden && detailRegion.textContent.trim().length > 0
      && detailBody.querySelectorAll("dt").length === 0
    );
    const detailMatchesFocusedRow = !expanded || !populated || (
      visibleRow?.dataset.highlighted === "true"
      && detailRegion.textContent.includes("long-diagnostic.bin")
      && detailRegion.textContent.includes(longDiagnostic)
    );
    const titleBounds = planReviewPanel.element.querySelector(".nami-plan-review__status-title")
      .getBoundingClientRect();
    const actionBounds = planReviewPanel.element.querySelector('[data-action="plan-again"]')
      .getBoundingClientRect();
    const titleActionAligned = titleBounds.height > 0 && actionBounds.height > 0
      && Math.abs((titleBounds.top + titleBounds.bottom) / 2
        - (actionBounds.top + actionBounds.bottom) / 2) <= Math.max(2, titleBounds.height / 2);
    const statusSummary = planReviewPanel.element.querySelector(".nami-plan-review__status-summary");
    const statusSummaryBounds = statusSummary?.getBoundingClientRect();
    const statusDetailsSameRow = statusSummaryBounds !== undefined
      && statusSummaryBounds.width > 0 && statusSummaryBounds.height > 0
      && disclosureBounds.left >= statusSummaryBounds.right - 1
      && Math.min(disclosureBounds.bottom, statusSummaryBounds.bottom)
        - Math.max(disclosureBounds.top, statusSummaryBounds.top)
        >= Math.min(disclosureBounds.height, statusSummaryBounds.height) / 2;
    const tableState = {
      offset: renderedGalleryTask.review.window.offset,
      scrollTop: viewport.scrollTop,
    };
    let collapseFocusRestored = true;
    let tableStatePreserved = true;
    if (expanded && populated) {
      detailRegion.focus();
      toggle.click();
      await new Promise((resolve) => requestAnimationFrame(resolve));
      collapseFocusRestored = diagnostics.hidden && document.activeElement === toggle;
      tableStatePreserved = renderedGalleryTask.review.window.offset === tableState.offset
        && viewport.scrollTop === tableState.scrollTop;
      toggle.click();
      await new Promise((resolve) => requestAnimationFrame(resolve));
    }
    const header = planReviewPanel.element.querySelector(".nami-plan-review__plan");
    const centralWidths = () => [header, summary, table].map((node) =>
      Number(node.getBoundingClientRect().width.toFixed(3)));
    const activeWidths = centralWidths();
    toggle.click();
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const oppositeWidths = centralWidths();
    toggle.click();
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const scrollPositions = () => [globalDiagnostics, detailRegion, viewport, planReviewPanel.element]
      .map((node) => Number(node.scrollTop.toFixed(3)));
    const savedCardScrolls = [globalDiagnostics.scrollTop, detailRegion.scrollTop];
    globalDiagnostics.scrollTop = 0;
    detailRegion.scrollTop = 0;
    const cardScrollPositions = [scrollPositions()];
    globalDiagnostics.scrollTop = globalDiagnostics.scrollHeight;
    cardScrollPositions.push(scrollPositions());
    detailRegion.scrollTop = detailRegion.scrollHeight;
    cardScrollPositions.push(scrollPositions());
    globalDiagnostics.scrollTop = savedCardScrolls[0];
    detailRegion.scrollTop = savedCardScrolls[1];
    const railWidth = galleryRail.element.getBoundingClientRect().width;
    if (diagnosticDefaultRailWidth === null) diagnosticDefaultRailWidth = railWidth;
    const railAligned = [...galleryRail.element.querySelectorAll(".nami-task-rail__row")].every((row) => {
      const card = row.querySelector(".nami-task-card");
      const close = row.querySelector(".nami-task-rail__close");
      const bounds = row.getBoundingClientRect();
      const paths = [...card.querySelectorAll(".nami-labeled-path__value")];
      return Math.abs(card.getBoundingClientRect().width - bounds.width) <= 1
        && close.getBoundingClientRect().right <= bounds.right + 1
        && paths.length === 2 && Math.abs(paths[0].getBoundingClientRect().left
          - paths[1].getBoundingClientRect().left) <= 1
        && [...card.querySelectorAll(".nami-task-card__status, .nami-task-card__paths, .nami-task-card__progress")]
          .every((field) => Math.abs(card.getBoundingClientRect().right
            - field.getBoundingClientRect().right - 18) <= 1);
    });
    const layoutResult = {
      case: caseName,
      block_size: Number(rootBounds.height.toFixed(3)),
      expanded,
      populated,
      logical_rows: populated ? 1000 : 0,
      loaded_rows: renderedGalleryTask.review.window.rows.length,
      disclosure_matches: toggle.getAttribute("aria-expanded") === String(expanded),
      diagnostics_visible: diagnostics.hidden === !expanded,
      rows_overflow: !populated || viewport.scrollHeight > viewport.clientHeight,
      scroll_advanced: !populated || viewport.scrollTop > 0,
      window_requested: !populated || galleryWindowRequests.some((offset) => Number.isInteger(offset)),
      window_adopted: !populated || adoptedOffset > initialOffset,
      viewport_bounded: viewport.clientHeight < (populated ? 1000 * 24 : rootBounds.height),
      row_height: populated ? (rowBounds?.height ?? 0) : 24,
      header_aligned: Math.abs(tableHeader.getBoundingClientRect().width - viewport.getBoundingClientRect().width) <= 1,
      whole_row_reachable: wholeRowReachable,
      both_columns_reachable: !expanded || visibleColumns.length === 2,
      row_activation_reachable: rowActivationReachable,
      placeholder_present: placeholderPresent,
      detail_matches_focused_row: detailMatchesFocusedRow,
      title_action_aligned: titleActionAligned,
      status_details_same_row: statusDetailsSameRow,
      details_rectangles: [header, summary, table, diagnostics, globalDiagnostics, detailRegion].map(rectangle),
      central_widths: expanded ? [oppositeWidths, activeWidths] : [activeWidths, oppositeWidths],
      card_scroll_positions: cardScrollPositions,
      rem_size: parseFloat(getComputedStyle(document.documentElement).fontSize),
      rail_widths: [diagnosticDefaultRailWidth, railWidth],
      rail_aligned: railAligned,
      header_scroll_observations: headerScrollObservations,
      global_content_rows: [issueRegion.clientHeight, issueRegion.scrollHeight,
        trashRegion.clientHeight, trashRegion.scrollHeight,
        issueRegion.getBoundingClientRect().bottom, trashRegion.getBoundingClientRect().top],
      collapse_focus_restored: collapseFocusRestored,
      table_state_preserved: tableStatePreserved,
      visible_count: visibleCount,
      root_fits: rootFits,
      table_usable: tableUsable,
      hidden_descendant_exempt: hiddenDescendantExempt,
      visible_collapsed_rejected: visibleCollapsedRejected,
      no_horizontal_control_clipping: noHorizontalControlClipping,
      cardinality_exact: cardinalityExact,
      issues_content_reachable: issuesContentReachable,
      trash_content_reachable: trashContentReachable,
      detail_content_reachable: detailContentReachable,
      issues_keyboard_reachable: issuesKeyboardReachable,
      trash_keyboard_reachable: trashKeyboardReachable,
      detail_keyboard_reachable: detailKeyboardReachable,
      readable_body: readableBody,
      disclosure_reachable: disclosureReachable,
      stale_facts_cleared: populated || (
        issueRegion.hidden && trashRegion.hidden && placeholderPresent
      ),
    };
    window.scrollTo(pageScroll.x, pageScroll.y);
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    return layoutResult;
  }

  async function inventoryPanelObservation() {
    const pageScroll = { x: window.scrollX, y: window.scrollY };
    const settled = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const checksum = "0123456789abcdef0123456789abcdef";
    const cases = ["verified", "unverified", "modified", "reappeared", "unsupported", "missing", "mismatched"];
    const rollup = { domain_count: 300, file_count: 300, size: 3000, size_overflow: false, size_partial: false,
      present: 298, unverified: 2, verified: 294, modified: 1, reappeared: 1, unsupported: 1,
      missing: 1, mismatched: 1, acknowledged: 0 };
    const rowAt = (index) => {
      const state = cases[index] ?? "verified";
      return { node_id: String(index + 1), row_id: String(index + 1), display: `evidence-${index}.txt`,
        depth: 0, visible_index: index, parent_visible_index: null, first_child_visible_index: null,
        position_in_set: index + 1, set_size: 300, expanded: null, is_container: false, kind: "file",
        presence: ["unsupported", "missing"].includes(state) ? state : "present",
        verification_state: ["unsupported", "missing", "reappeared"].includes(state) ? "unverified" : state,
        reappeared: state === "reappeared", acknowledged: false, size: 10, mtime_ns: "1000000000",
        has_baseline: state !== "unverified", recorded_checksum: state === "unverified" ? null : checksum,
        warning: null, rollup };
    };
    const windowAt = (offset) => ({ offset, total: 300,
      rows: Array.from({ length: Math.min(64, 300 - offset) }, (_, index) => rowAt(offset + index)) });
    const review = { summary: { root_path: "C:\\recorded", request_id: "1".repeat(32),
      rollup, visible_row_count: 300, filters: [], scan_scope: { kind: "location" }, scan_complete: true,
      observed_count: 299, missing_count: 1, warning_count: 0, search_query: "",
      sort_column: "path", sort_direction: "ascending" }, window: windowAt(0), detail: null,
      pending: null, message: null, queuedSearchQuery: null };
    const inventoryTask = { taskId: "task-" + "2".repeat(32), requestId: "1".repeat(32),
      sessionState: "completed", sessionReleased: true, taskKind: "inventory", inventoryReview: review };
    const requests = [];
    const panel = createInventoryReviewPanel({
      onWindow: async (_owner, offset) => { requests.push(offset); return windowAt(offset); },
      onDetail() {}, onViewChange() {}, onRefresh() {}, onReload() {}, onCheckOutcome() {}, onVisibility() {},
    });
    const root = panel.element;
    root.dataset.gallerySection = "inventory_panel";
    root.style.gridColumn = "1 / -1";
    root.style.inlineSize = "1000px";
    root.style.blockSize = "640px";
    app.append(root);
    panel.render(inventoryTask);
    await settled();
    const setupReference = document.createElement("section");
    setupReference.className = "nami-plan-review";
    setupReference.style.display = "block";
    setupReference.style.blockSize = "auto";
    setupReference.append(planReviewPanel.element.querySelector(".nami-plan-review__plan").cloneNode(true));
    app.append(setupReference);
    const setupHeights = [];
    for (const width of [1000, 640]) {
      root.style.inlineSize = `${width}px`;
      setupReference.style.inlineSize = `${width}px`;
      await settled();
      setupHeights.push([root, setupReference].map((value) =>
        Number(value.querySelector(".nami-plan-review__plan").getBoundingClientRect().height.toFixed(3))));
    }
    setupReference.remove();
    root.style.inlineSize = "1000px";
    await settled();
    const statusLine = root.querySelector(".nami-inventory-review__status-line");
    const statusCard = root.querySelector(".nami-plan-review__summary");
    const track = root.querySelector(".nami-plan-review__progress");
    const statusEvidence = { single_line: statusCard.querySelectorAll(":scope > p").length === 1 };
    panel.render({ ...inventoryTask, sessionState: "active", sessionReleased: false, inventoryLoading: true });
    await settled();
    statusEvidence.loading_same_line = root.querySelector(".nami-inventory-review__status-line") === statusLine
      && statusLine.textContent.includes("Loading inventory view…")
      && statusCard.querySelectorAll(":scope > p").length === 1;
    statusEvidence.active_animation = getComputedStyle(track.firstElementChild).animationName;
    statusEvidence.active_indeterminate = track.classList.contains("nami-progress--indeterminate");
    panel.render(inventoryTask);
    await settled();
    statusEvidence.terminal_animation = getComputedStyle(track.firstElementChild).animationName;
    statusEvidence.terminal_track_visible = track.getBoundingClientRect().height > 0;
    statusEvidence.track_height = Number(track.getBoundingClientRect().height.toFixed(3));
    statusEvidence.terminal_value = track.firstElementChild.style.getPropertyValue("--nami-progress-value");
    const headers = [...root.querySelectorAll(".nami-inventory-review__columns > div")];
    const viewport = root.querySelector(".nami-inventory-review__rows");
    const widths = () => headers.map((value) => Number(value.getBoundingClientRect().width.toFixed(3)));
    const firstRow = () => viewport.querySelector(".nami-inventory-row");
    const rectangle = (value) => {
      const rect = value.getBoundingClientRect();
      return [rect.left, rect.top, rect.right, rect.bottom].map((number) => Number(number.toFixed(3)));
    };
    const firstWidths = widths();
    const rowWidths = [...firstRow().children].map((value) => Number(value.getBoundingClientRect().width.toFixed(3)));
    const headerPositions = headers.map(rectangle);
    const rowPositions = [...firstRow().children].map(rectangle);
    const statusRectangles = [".nami-plan-review__status-title", ".nami-plan-review__actions > .nami-inventory-review__actions",
      ".nami-plan-review__status-summary", '[data-action="inventory-details"]'].map((selector) => rectangle(root.querySelector(selector)));
    const scrollOwners = { outer_x: getComputedStyle(root.querySelector(".nami-inventory-review__list")).overflowX,
      body_x: getComputedStyle(viewport).overflowX, body_y: getComputedStyle(viewport).overflowY };
    const labels = cases.map((name, index) => {
      const state = viewport.querySelector(`[data-node-id="${index + 1}"] .nami-file-state-label`);
      const style = getComputedStyle(state);
      return { case: name, text: state.textContent, foreground: style.color, background: style.backgroundColor,
        height: Number(state.getBoundingClientRect().height.toFixed(3)) };
    });
    const checksumCell = firstRow().querySelector(".nami-inventory-row__checksum");
    const checksumEvidence = { text: checksumCell.textContent, title: checksumCell.title,
      absent: viewport.querySelector('[data-node-id="2"] .nami-inventory-row__checksum').textContent };
    root.style.inlineSize = "1200px";
    await settled();
    const grownWidths = widths();
    const handle = headers[0].querySelector("[role=separator]");
    handle.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowLeft", bubbles: true }));
    await settled();
    const manualBefore = widths();
    handle.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
    await settled();
    const manualAfter = widths();
    const diagnostics = root.querySelector(".nami-inventory-review__diagnostics");
    const initiallyHidden = diagnostics.hidden;
    const toggle = root.querySelector('[data-action="inventory-details"]');
    toggle.click();
    await settled();
    const rootBounds = root.getBoundingClientRect();
    const detailsBounds = diagnostics.getBoundingClientRect();
    const global = diagnostics.querySelector(".nami-plan-review__global-diagnostics");
    const item = diagnostics.querySelector(".nami-plan-review__detail");
    const detailEvidence = { initially_hidden: initiallyHidden, expanded: !diagnostics.hidden,
      root_height: rootBounds.height, column_height: detailsBounds.height,
      root_width: rootBounds.width, column_width: detailsBounds.width,
      global_overflow: getComputedStyle(global).overflowY, item_overflow: getComputedStyle(item).overflowY,
      placeholder: item.textContent.includes("Select an item to see its details.") };
    item.focus();
    toggle.click();
    detailEvidence.focus_restored = document.activeElement === toggle && diagnostics.hidden;
    await settled();
    const viewportHeight = viewport.clientHeight;
    viewport.scrollTop = 250 * 28;
    viewport.dispatchEvent(new Event("scroll"));
    await settled();
    await settled();
    const evidence = { headers: headers.map((value) => value.textContent), checkbox_count: root.querySelectorAll('input[type="checkbox"]').length,
      switcher: [...root.querySelectorAll(".nami-segmented__item")].map((value) => ({ text: value.textContent,
        selected: value.ariaChecked, disabled: value.disabled })), labels, checksum: checksumEvidence,
      first_widths: firstWidths, row_widths: rowWidths, grown_widths: grownWidths,
      header_positions: headerPositions, row_positions: rowPositions,
      status_rectangles: statusRectangles, setup_heights: setupHeights, status: statusEvidence, scroll_owners: scrollOwners,
      manual_before: manualBefore, manual_after: manualAfter, details: detailEvidence,
      refresh_on_status: [...root.querySelectorAll('[data-action="inventory-refresh"], [data-action="inventory-refresh-selected"]')]
        .every((value) => value.closest(".nami-plan-review__summary") !== null),
      root_fits: root.scrollHeight <= root.clientHeight + 1,
      viewport_height: viewportHeight, viewport_scroll_height: viewport.scrollHeight,
      adopted_offset: review.window.offset, window_requests: requests,
      row_height: firstRow().getBoundingClientRect().height };
    panel.dispose();
    root.remove();
    window.scrollTo(pageScroll.x, pageScroll.y);
    await settled();
    return evidence;
  }
  galleryMeasurementStep = "inventory_panel";
  const inventoryPanelEvidence = await inventoryPanelObservation();
  const diagnosticLayoutEvidence = [];
  // These Plan-pane block sizes model the available area at default and supported-minimum
  // windows; they do not set a product viewport or restore the retired file-list width.
  const minimumDiagnosticBlockSize = 480;
  const defaultDiagnosticBlockSize = minimumDiagnosticBlockSize + 160;
  // The native minimum fixture height is separate from the retired file-list width guard.
  const minimumNativeWindowHeight = minimumDiagnosticBlockSize + 160;
  galleryMeasurementStep = "diagnostic_default_folded_empty";
  diagnosticLayoutEvidence.push(
    await diagnosticLayout("default-folded-empty", defaultDiagnosticBlockSize, false, false),
  );
  galleryMeasurementStep = "diagnostic_default_folded_populated";
  diagnosticLayoutEvidence.push(
    await diagnosticLayout("default-folded-populated", defaultDiagnosticBlockSize, false, true),
  );
  galleryMeasurementStep = "diagnostic_default_expanded_empty";
  diagnosticLayoutEvidence.push(
    await diagnosticLayout("default-expanded-empty", defaultDiagnosticBlockSize, true, false),
  );
  galleryMeasurementStep = "diagnostic_default_expanded_populated";
  diagnosticLayoutEvidence.push(
    await diagnosticLayout("default-expanded-populated", defaultDiagnosticBlockSize, true, true),
  );
  const defaultWindowSize = {
    outer_width: window.outerWidth,
    outer_height: window.outerHeight,
  };
  const nativeDefault = await dispatchInteractive(
    "test_report",
    Object.freeze({ phase: "diagnostic_status" }),
    validNativeFailureSnapshot,
  );
  let minimumWindowEvidence = null;
  planReviewPanel.element.style.blockSize = "480px";
  planReviewPanel.render(planReviewTask);
  galleryStage = "control_matrix";
  const controlsSection = document.createElement("section");
  controlsSection.className = "nami-card";
  controlsSection.dataset.gallerySection = "controls";
  app.append(controlsSection);
  for (const definition of CONTROL_CASES) {
    for (const state of CONTROL_STATES) {
      const { root, target } = controlElement(definition, state.key);
      const element = target;
      element.id = `gallery-control-${definition.key}-${state.key}`;
      const specimen = document.createElement("div");
      specimen.dataset.gallerySpecimen = `${definition.key}-${state.key}`;
      const label = document.createElement("span");
      renderText(label, `${definition.key.replaceAll("_", " ")} — ${state.key}`);
      specimen.append(label, root);
      controlsSection.append(specimen);
    }
  }
  const mixedCheckbox = document.createElement("input");
  mixedCheckbox.className = "nami-checkbox";
  mixedCheckbox.type = "checkbox";
  mixedCheckbox.indeterminate = true;
  mixedCheckbox.setAttribute("aria-checked", "mixed");
  mixedCheckbox.setAttribute("aria-label", "Mixed tri-state specimen");
  controlsSection.append(mixedCheckbox);
  const uncheckedCheckbox = document.createElement("input");
  uncheckedCheckbox.className = "nami-checkbox";
  uncheckedCheckbox.type = "checkbox";
  uncheckedCheckbox.setAttribute("aria-label", "Unchecked checkbox specimen");
  controlsSection.append(uncheckedCheckbox);
  const checkedCheckbox = document.createElement("input");
  checkedCheckbox.className = "nami-checkbox";
  checkedCheckbox.type = "checkbox";
  checkedCheckbox.checked = true;
  checkedCheckbox.setAttribute("aria-label", "Checked checkbox specimen");
  controlsSection.append(checkedCheckbox);

  const hdrIsolation = document.createElement("section");
  hdrIsolation.className = "nami-card";
  hdrIsolation.dataset.gallerySection = "hdr_flyout_isolation";
  const hdrHeading = document.createElement("h2");
  renderText(hdrHeading, "HDR flyout isolation");
  hdrIsolation.append(hdrHeading);
  for (const [labelText, isolate] of [
    ["Normal translucent surface with shadow", "normal"],
    ["Translucent surface without shadow", "shadowless"],
    ["Opaque surface with shadow", "opaque"],
  ]) {
    const surface = document.createElement("div");
    surface.className = "nami-menu";
    surface.dataset.galleryHdrIsolate = isolate;
    if (isolate === "shadowless") {
      surface.style.boxShadow = "none";
    } else {
      surface.style.boxShadow = "var(--elevation-8)";
      if (isolate === "opaque") {
        surface.style.background = "var(--color-flyout-background-solid)";
      }
    }
    const item = document.createElement("button");
    item.className = "nami-menu__item";
    item.type = "button";
    renderText(item, labelText);
    surface.append(item);
    hdrIsolation.append(surface);
  }
  controlsSection.append(hdrIsolation);

  const ordinaryThemeOption = document.querySelector("#theme-option-system");
  const pressedThemeOptionSource = document.querySelector(
    `#theme-option-${alternateTheme}`,
  );
  if (
    !(ordinaryThemeOption instanceof HTMLElement)
    || !(pressedThemeOptionSource instanceof HTMLElement)
  ) {
    throw new TypeError("production combobox option probes are unavailable");
  }
  const ordinaryOptionRestBackground = getComputedStyle(
    ordinaryThemeOption,
  ).backgroundColor;
  const optionStatePopup = document.createElement("div");
  optionStatePopup.className = "nami-combobox__popup";
  optionStatePopup.setAttribute("aria-hidden", "true");
  optionStatePopup.style.position = "fixed";
  optionStatePopup.style.insetInlineStart = "-10000px";
  optionStatePopup.style.insetBlockStart = "0";
  optionStatePopup.style.display = "grid";
  const hoveredThemeOption = ordinaryThemeOption.cloneNode(true);
  const pressedThemeOption = pressedThemeOptionSource.cloneNode(true);
  hoveredThemeOption.id = "gallery-theme-option-hover";
  pressedThemeOption.id = "gallery-theme-option-pressed";
  optionStatePopup.append(hoveredThemeOption, pressedThemeOption);
  document.body.append(optionStatePopup);

  const pseudoTargets = CONTROL_CASES.flatMap((definition) => [
    { selector: `#gallery-control-${definition.key}-hover`, classes: ["hover"] },
    { selector: `#gallery-control-${definition.key}-pressed`, classes: ["hover", "active"] },
    { selector: `#gallery-control-${definition.key}-focused`, classes: ["focus", "focus-visible"] },
  ]);
  pseudoTargets.push(
    { selector: "#gallery-theme-option-hover", classes: ["hover"] },
    {
      selector: "#gallery-theme-option-pressed",
      classes: ["hover", "active"],
    },
  );
  galleryStage = "pseudo_states";
  galleryMeasurementStep = "pseudo_state_settlement";
  galleryFailureReason = "native_pseudo_pending";
  await dispatchInteractive(
    "test_report",
    Object.freeze({ phase: "prepare", targets: pseudoTargets }),
    validAccepted,
  );
  const pseudoDeadline = performance.now() + 5000;
  while (globalThis.__namiGalleryPseudoReady !== true) {
    if (performance.now() >= pseudoDeadline) {
      throw new Error("native pseudo-state preparation timed out");
    }
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  await new Promise((resolve) => setTimeout(resolve, PSEUDO_STATE_SETTLE_MS));

  galleryStage = "measurement";
  galleryMeasurementStep = "control_styles";
  galleryFailureReason = "control_invariant";
  const controlsSurfaceProbe = document.createElement("div");
  controlsSurfaceProbe.style.background = "var(--color-card-background-solid)";
  controlsSurfaceProbe.style.position = "fixed";
  controlsSurfaceProbe.style.visibility = "hidden";
  document.body.append(controlsSurfaceProbe);
  const controlsSurrounding = getComputedStyle(controlsSurfaceProbe).backgroundColor;
  controlsSurfaceProbe.remove();
  const controls = [];
  let nonessentialMax = 0;
  let indeterminateIterationCount = "";
  for (const definition of CONTROL_CASES) {
    for (const state of CONTROL_STATES) {
      const element = document.querySelector(`#gallery-control-${definition.key}-${state.key}`);
      if (!(element instanceof HTMLElement)) {
        throw new TypeError("gallery control specimen is unavailable");
      }
      const style = getComputedStyle(element);
      const thumbStyle = getComputedStyle(element, "::after");
      const thumbWidth = Number.parseFloat(thumbStyle.width);
      const thumbHeight = Number.parseFloat(thumbStyle.height);
      const thumbInlineStart = Number.parseFloat(thumbStyle.insetInlineStart);
      const thumbBlockStart = Number.parseFloat(thumbStyle.insetBlockStart);
      const borderInlineStart = Number.parseFloat(style.borderInlineStartWidth);
      const borderBlockStart = Number.parseFloat(style.borderBlockStartWidth);
      const transform = thumbStyle.transform === "none"
        ? new DOMMatrixReadOnly()
        : new DOMMatrixReadOnly(thumbStyle.transform);
      const controlWidth = Number.parseFloat(style.width);
      const motionTarget = definition.key.startsWith("progress_")
        ? element.querySelector(".nami-progress__bar") || element
        : element;
      const motionStyle = getComputedStyle(motionTarget);
      const root = ["context_menu", "segmented_control"].includes(definition.key)
        ? element.parentElement
        : element;
      const rootStyle = root instanceof HTMLElement ? getComputedStyle(root) : style;
      nonessentialMax = Math.max(
        nonessentialMax,
        durationMilliseconds(motionStyle.transitionDuration),
        durationMilliseconds(motionStyle.animationDuration),
      );
      if (definition.key === "progress_indeterminate") {
        indeterminateIterationCount = motionStyle.animationIterationCount;
      }
      const outlineVisible = style.outlineStyle !== "none" &&
        parseFloat(style.outlineWidth) > 0;
      controls.push({
        control: definition.key,
        state: state.key,
        label: `${definition.key.replaceAll("_", " ")} — ${state.key}`,
        foreground: style.color,
        background: style.backgroundColor,
        background_image: style.backgroundImage,
        fill_background: motionStyle.backgroundColor,
        border: style.borderColor,
        border_width: style.borderWidth,
        border_style: style.borderStyle,
        border_block_start: style.borderBlockStartColor,
        border_block_end: style.borderBlockEndColor,
        border_block_start_width: style.borderBlockStartWidth,
        border_block_end_width: style.borderBlockEndWidth,
        root_border: rootStyle.borderColor,
        root_border_width: rootStyle.borderWidth,
        root_border_style: rootStyle.borderStyle,
        root_background: rootStyle.backgroundColor,
        boundary: outlineVisible ? style.outlineColor : style.borderColor,
        outline_width: style.outlineWidth,
        outline_color: style.outlineColor,
        outline_style: style.outlineStyle,
        box_shadow: style.boxShadow,
        surrounding: controlsSurrounding,
        visual_filter: style.filter,
        opacity: style.opacity,
        transform: style.transform,
        transition_duration: motionStyle.transitionDuration,
        animation_duration: motionStyle.animationDuration,
        animation_name: motionStyle.animationName,
        control_width: style.width,
        control_height: style.height,
        thumb_background: thumbStyle.backgroundColor,
        thumb_width: thumbStyle.width,
        thumb_height: thumbStyle.height,
        thumb_inset_block_start: thumbStyle.insetBlockStart,
        thumb_inset_inline_start: thumbStyle.insetInlineStart,
        thumb_transform: thumbStyle.transform,
        thumb_center_block: String(borderBlockStart + thumbBlockStart + transform.m42 + (thumbHeight / 2)),
        thumb_edge_start: String(borderInlineStart + thumbInlineStart),
        thumb_edge_end: String(controlWidth - borderInlineStart - thumbInlineStart - thumbWidth),
      });
    }
  }

  const lifecycleProgress = lifecycleProgressSpecimens.map(({
    definition,
    progress,
    bar,
    motionBar,
  }) => {
    const progressStyle = getComputedStyle(progress);
    const barStyle = getComputedStyle(bar);
    const motionStyle = getComputedStyle(motionBar);
    const motionFrozen = motionStyle.animationName === "none"
      || motionStyle.animationPlayState === "paused"
      || durationMilliseconds(motionStyle.animationDuration) === 0;
    return {
      case: definition.key,
      lifecycle: definition.lifecycle,
      hue: definition.hue,
      expected_frozen: definition.frozen,
      motion_frozen: motionFrozen,
      track_background: progressStyle.backgroundColor,
      fill_background: barStyle.backgroundColor,
      animation_name: motionStyle.animationName,
      animation_duration: motionStyle.animationDuration,
      animation_iteration_count: motionStyle.animationIterationCount,
      animation_play_state: motionStyle.animationPlayState,
    };
  });

  const planSectionStyle = getComputedStyle(planSection);
  const planSectionContentWidth = planSection.clientWidth
    - parseFloat(planSectionStyle.paddingLeft)
    - parseFloat(planSectionStyle.paddingRight);
  const galleryUsesWorkArea = planSectionStyle.gridArea === "work";
  function toneAndKey(cell) {
    const semantic = cell.matches(
      "[data-intent], [data-integrity], [data-lifecycle]",
    )
      ? cell
      : cell.querySelector(
        "[data-intent], [data-integrity], [data-lifecycle]",
      );
    if (!(semantic instanceof HTMLElement)) {
      return ["", ""];
    }
    if (semantic.dataset.intent !== undefined) {
      return ["intent", semantic.dataset.intent];
    }
    if (semantic.dataset.integrity !== undefined) {
      return ["integrity", semantic.dataset.integrity];
    }
    if (semantic.dataset.lifecycle !== undefined) {
      return ["lifecycle", semantic.dataset.lifecycle];
    }
    return ["", ""];
  }

  function collectFileListEvidence(specimen, definitions) {
    galleryMeasurementStep = "file_list_specimen";
    galleryFailureReason = "file_list_invariant";
    const {
      list,
      grid,
      header,
      body,
      masterCheckbox,
    } = specimen;
    const rootFontSize = parseFloat(
      getComputedStyle(document.documentElement).fontSize,
    );
    const fillsWorkArea = Math.abs(
      list.getBoundingClientRect().width - planSectionContentWidth,
    ) < 0.5;
    galleryMeasurementStep = "hierarchy_selection";
    galleryFailureReason = "hierarchy_invariant";
    const folderDisclosure = body.querySelector(
      '[data-folder="true"] .nami-file-row__disclosure',
    );
    const childRows = [...body.querySelectorAll("[data-gallery-parent]")];
    if (!(folderDisclosure instanceof HTMLButtonElement) || childRows.length < 2) {
      throw new TypeError("gallery hierarchy specimen is unavailable");
    }
    folderDisclosure.click();
    const collapseHidesChildren = childRows.every(
      (row) => row.hidden && getComputedStyle(row).display === "none",
    );
    folderDisclosure.click();
    const collapseRestoresChildren = childRows.every(
      (row) => !row.hidden && getComputedStyle(row).display !== "none",
    );
    const folderCheckbox = body.querySelector(
      '[data-folder="true"] .nami-checkbox',
    );
    const childCheckboxes = childRows.map((row) =>
      row.querySelector(".nami-checkbox")
    );
    const uncheckedChild = childCheckboxes.find(
      (checkbox) => checkbox instanceof HTMLInputElement && !checkbox.checked,
    );
    if (
      !(folderCheckbox instanceof HTMLInputElement)
      || !(uncheckedChild instanceof HTMLInputElement)
    ) {
      throw new TypeError("gallery partial selection specimen is unavailable");
    }
    uncheckedChild.checked = true;
    uncheckedChild.dispatchEvent(new Event("change", { bubbles: true }));
    const childSelectionSelectsFolder = folderCheckbox.checked
      && !folderCheckbox.indeterminate
      && folderCheckbox.ariaChecked === "true";
    uncheckedChild.checked = false;
    uncheckedChild.dispatchEvent(new Event("change", { bubbles: true }));
    const childSelectionRestoresMixed = !folderCheckbox.checked
      && folderCheckbox.indeterminate
      && folderCheckbox.ariaChecked === "mixed";
    const rowCheckboxes = [...body.querySelectorAll(
      '.nami-checkbox[type="checkbox"]',
    )];
    const selectionSnapshot = rowCheckboxes.map((checkbox) => ({
      checked: checkbox.checked,
      indeterminate: checkbox.indeterminate,
      ariaChecked: checkbox.getAttribute("aria-checked"),
    }));
    galleryMeasurementStep = "master_selection";
    galleryFailureReason = "selection_invariant";
    const masterInitiallyMixed = !masterCheckbox.checked
      && masterCheckbox.indeterminate
      && masterCheckbox.ariaChecked === "mixed";
    masterCheckbox.checked = true;
    masterCheckbox.dispatchEvent(new Event("change", { bubbles: true }));
    const masterSelectsAll = rowCheckboxes.every(
      (checkbox) => checkbox.disabled || (checkbox.checked && !checkbox.indeterminate),
    ) && masterCheckbox.checked && !masterCheckbox.indeterminate;
    masterCheckbox.checked = false;
    masterCheckbox.dispatchEvent(new Event("change", { bubbles: true }));
    const masterDeselectsAll = rowCheckboxes.every(
      (checkbox) => checkbox.disabled || (!checkbox.checked && !checkbox.indeterminate),
    ) && !masterCheckbox.checked && !masterCheckbox.indeterminate;
    for (const [index, checkbox] of rowCheckboxes.entries()) {
      const snapshot = selectionSnapshot[index];
      checkbox.checked = snapshot.checked;
      checkbox.indeterminate = snapshot.indeterminate;
      if (snapshot.ariaChecked === null) {
        checkbox.removeAttribute("aria-checked");
      } else {
        checkbox.setAttribute("aria-checked", snapshot.ariaChecked);
      }
    }
    masterCheckbox.checked = false;
    masterCheckbox.indeterminate = true;
    masterCheckbox.ariaChecked = "mixed";
    const selectionResizer = header.querySelector(
      '.nami-file-list__column-resizer[data-column="selection"]',
    );
    const nameResizer = header.querySelector(
      '.nami-file-list__column-resizer[data-column="name"]',
    );
    if (
      !(selectionResizer instanceof HTMLElement)
      || !(nameResizer instanceof HTMLElement)
    ) {
      throw new TypeError("gallery column resize specimen is unavailable");
    }
    const geometry = () => {
      const cells = [...header.children];
      const bounds = cells.map((cell) => cell.getBoundingClientRect());
      const listBounds = list.getBoundingClientRect();
      return {
        widths: bounds.map((bound) => Number(bound.width.toFixed(3))),
        lefts: bounds.map((bound) => Number(bound.left.toFixed(3))),
        right: Number(bounds[bounds.length - 1].right.toFixed(3)),
        rightSpan: Number(
          (bounds[bounds.length - 1].right - listBounds.left).toFixed(3),
        ),
        gridWidth: Number(grid.getBoundingClientRect().width.toFixed(3)),
        listWidth: Number(listBounds.width.toFixed(3)),
      };
    };
    const columnsAlign = () => {
      const row = body.firstElementChild;
      if (!(row instanceof HTMLElement)) return false;
      const headerLefts = [...header.children].map(
        (cell) => cell.getBoundingClientRect().left,
      );
      const bodyLefts = [...row.children].map(
        (cell) => cell.getBoundingClientRect().left,
      );
      return headerLefts.length === bodyLefts.length
        && headerLefts.every(
          (left, index) => Math.abs(left - bodyLefts[index]) <= 0.5,
        );
    };
    const initialLayoutFrozen = grid.dataset.columnsFrozen === "true";
    planSection.style.setProperty("inline-size", "70rem");
    const initialGeometry = geometry();
    const normalColumnsAlign = columnsAlign();
    nameResizer.dispatchEvent(new PointerEvent("pointerdown", {
      bubbles: true,
      clientX: 200,
    }));
    const frozenGeometry = geometry();
    galleryMeasurementStep = "column_resize";
    galleryFailureReason = "column_resize_invariant";
    const requestedPointerDelta = -Math.min(
      8,
      Math.max(0, frozenGeometry.widths[1] - rootFontSize * 12),
    );
    window.dispatchEvent(new PointerEvent("pointermove", {
      clientX: 200 + requestedPointerDelta,
    }));
    window.dispatchEvent(new PointerEvent("pointerup", {
      clientX: 200 + requestedPointerDelta,
    }));
    const pointerGeometry = geometry();
    const resizedColumnsAlign = columnsAlign();
    const resizeDelta = pointerGeometry.widths[1] - frozenGeometry.widths[1];
    const notesIndex = header.children.length - 1;
    const notesResizeDelta = pointerGeometry.widths[notesIndex]
      - frozenGeometry.widths[notesIndex];
    const columnResizeChangesWidth = Math.abs(resizeDelta) > 0.5;

    selectionResizer.dispatchEvent(new KeyboardEvent("keydown", {
      bubbles: true,
      key: "ArrowRight",
    }));
    const keyboardGeometry = geometry();
    const keyboardResizeDelta = keyboardGeometry.widths[0]
      - pointerGeometry.widths[0];
    const keyboardNotesDelta = keyboardGeometry.widths[notesIndex]
      - pointerGeometry.widths[notesIndex];

    const availableNameWidth = keyboardGeometry.widths[1] - rootFontSize * 12;
    const viewportResizeAmount = Math.min(32, Math.max(0, availableNameWidth / 2));
    list.style.setProperty(
      "inline-size",
      `${keyboardGeometry.listWidth - viewportResizeAmount}px`,
    );
    const viewportNarrowGeometry = geometry();
    const narrowColumnsAlign = columnsAlign();
    list.style.removeProperty("inline-size");
    const viewportRestoredGeometry = geometry();

    nameResizer.dispatchEvent(new PointerEvent("pointerdown", {
      bubbles: true,
      clientX: 200,
    }));
    window.dispatchEvent(new PointerEvent("pointermove", { clientX: 10200 }));
    window.dispatchEvent(new PointerEvent("pointerup", { clientX: 10200 }));
    const notesMinimumGeometry = geometry();

    nameResizer.dispatchEvent(new PointerEvent("pointerdown", {
      bubbles: true,
      clientX: 200,
    }));
    window.dispatchEvent(new PointerEvent("pointermove", { clientX: -9800 }));
    window.dispatchEvent(new PointerEvent("pointerup", { clientX: -9800 }));
    const nameMinimumGeometry = geometry();

    list.style.setProperty("inline-size", "36rem");
    const constrainedGeometry = geometry();
    const constrainedColumnsAlign = columnsAlign();
    const renderedRows = [...body.children];
    galleryMeasurementStep = "file_rows";
    galleryFailureReason = "file_row_invariant";
    const rows = renderedRows.map((row, index) => {
      if (!(row instanceof HTMLElement)) {
        throw new TypeError("gallery file row is unavailable");
      }
      const definition = definitions[index];
      const cells = [...row.children];
      const checkbox = row.querySelector(".nami-checkbox");
      const name = row.querySelector('.nami-file-row__name');
      const size = row.querySelector('.nami-file-row__size');
      const primary = row.querySelector('[data-file-column="primary"]');
      const secondary = row.querySelector('[data-file-column="secondary"]');
      const primaryLabel = primary?.querySelector(".nami-file-state-label");
      const inlineProgress = primary?.querySelector(".nami-progress--inline");
      const notes = row.querySelector('.nami-file-row__notes');
      if (
        definition === undefined
        || !(checkbox instanceof HTMLInputElement)
        || !(name instanceof HTMLElement)
        || !(size instanceof HTMLElement)
        || !(primary instanceof HTMLElement)
        || !(secondary instanceof HTMLElement)
        || !(
          primaryLabel instanceof HTMLElement
          || inlineProgress instanceof HTMLElement
        )
        || !(notes instanceof HTMLElement)
        || cells.length !== header.children.length
        || !cells.every((cell) => cell instanceof HTMLElement)
      ) {
        throw new TypeError("gallery file row structure is unavailable");
      }
      const [primaryTone, primaryKey] = toneAndKey(primary);
      const [secondaryTone, secondaryKey] = toneAndKey(secondary);
      const primaryVisual = inlineProgress instanceof HTMLElement
        ? inlineProgress
        : primaryLabel;
      const primaryStyle = getComputedStyle(
        inlineProgress instanceof HTMLElement ? primary : primaryVisual,
      );
      const primaryAliases = resolvedStateAliases(primary);
      const primaryColor = inlineProgress instanceof HTMLElement
        ? primaryAliases.foreground
        : primaryStyle.color;
      const primaryBackground = inlineProgress instanceof HTMLElement
        ? primaryAliases.background
        : primaryStyle.backgroundColor;
      const primaryBounds = primaryVisual.getBoundingClientRect();
      const primaryCellBounds = primary.getBoundingClientRect();
      const primaryCellStyle = getComputedStyle(primary);
      const progressBar = inlineProgress?.querySelector(".nami-progress__bar");
      const progressStyle = inlineProgress instanceof HTMLElement
        ? getComputedStyle(inlineProgress)
        : null;
      const progressBarStyle = progressBar instanceof HTMLElement
        ? getComputedStyle(progressBar)
        : null;
      const secondaryColor = getComputedStyle(secondary).color;
      const disclosure = row.querySelector(".nami-file-row__disclosure");
      const checkboxBounds = checkbox.getBoundingClientRect();
      const rowStyle = getComputedStyle(row);
      return {
        case: definition.key,
        role: row.getAttribute("role"),
        cell_roles: cells.map((cell) => cell.getAttribute("role")),
        checkbox_label: checkbox.getAttribute("aria-label"),
        checkbox_checked: checkbox.checked,
        checkbox_disabled: checkbox.disabled,
        checkbox_indeterminate: checkbox.indeterminate,
        checkbox_aria_checked: checkbox.getAttribute("aria-checked"),
        checkbox_width: checkboxBounds.width,
        checkbox_height: checkboxBounds.height,
        depth: Number(row.style.getPropertyValue("--nami-file-depth")),
        folder: row.dataset.folder === "true",
        expanded: disclosure instanceof HTMLButtonElement
          ? disclosure.ariaExpanded
          : null,
        name: row.querySelector(".nami-file-row__name-text")?.textContent,
        size: size.textContent,
        primary: inlineProgress instanceof HTMLElement
          ? inlineProgress.getAttribute("aria-label")
          : primary.textContent,
        primary_tone: primaryTone,
        primary_key: primaryKey,
        primary_form: inlineProgress instanceof HTMLElement
          ? "progress"
          : primaryTone === ""
          ? ""
          : transparentColor(primaryBackground) ? "text" : "fill",
        secondary: secondary.textContent,
        secondary_tone: secondaryTone,
        secondary_key: secondaryKey,
        notes: notes.textContent,
        background: rowStyle.backgroundColor,
        primary_foreground: primaryColor,
        primary_background: primaryBackground,
        primary_height: primaryBounds.height,
        primary_width: primaryBounds.width,
        primary_cell_width: primaryCellBounds.width,
        primary_cell_padding_left: parseFloat(primaryCellStyle.paddingLeft),
        primary_cell_padding_right: parseFloat(primaryCellStyle.paddingRight),
        primary_progress_value: inlineProgress instanceof HTMLElement
          ? Number(inlineProgress.getAttribute("aria-valuenow"))
          : null,
        primary_progress_bar_width: progressBar instanceof HTMLElement
          ? progressBar.getBoundingClientRect().width
          : 0,
        primary_progress_track: progressStyle?.backgroundColor ?? "",
        primary_progress_fill: progressBarStyle?.backgroundColor ?? "",
        primary_alias_foreground: primaryTone === ""
          ? primaryColor
          : primaryAliases.foreground,
        primary_alias_background: primaryTone === ""
          ? primaryBackground
          : primaryAliases.background,
        secondary_color: secondaryColor,
        secondary_alias_color: secondaryTone === ""
          ? secondaryColor
          : resolvedStateAliases(secondary).foreground,
        cell_backgrounds: cells.map(
          (cell) => getComputedStyle(cell).backgroundColor,
        ),
        cells_transparent: cells.every(
          (cell) => transparentColor(getComputedStyle(cell).backgroundColor),
        ),
        column_lefts: cells.map(
          (cell) => Number(cell.getBoundingClientRect().left.toFixed(3)),
        ),
        name_padding_left: Number(
          parseFloat(getComputedStyle(name).paddingLeft).toFixed(3),
        ),
        row_height: row.getBoundingClientRect().height,
        font_size: parseFloat(rowStyle.fontSize),
      };
    });
    const headerCells = [...header.children];
    const bodyBounds = body.getBoundingClientRect();
    const lastRow = renderedRows[renderedRows.length - 1];
    galleryMeasurementStep = "file_list_structure";
    galleryFailureReason = "file_list_invariant";
    if (
      !(lastRow instanceof HTMLElement)
      || headerCells.length !== header.children.length
      || !headerCells.every((cell) => cell instanceof HTMLElement)
    ) {
      throw new TypeError("gallery file list structure is unavailable");
    }
    const rowsHeight = renderedRows.reduce(
      (total, row) => total + row.getBoundingClientRect().height,
      0,
    );
    const headerStyle = getComputedStyle(header);
    const bodyStyle = getComputedStyle(body);
    const headerScrollbarStyle = getComputedStyle(
      header,
      "::-webkit-scrollbar",
    );
    const bodyScrollbarStyle = getComputedStyle(
      body,
      "::-webkit-scrollbar",
    );
    grid.style.setProperty("block-size", "12rem");
    const retainedRows = [...body.children];
    body.replaceChildren();
    const emptyHeaderClientWidth = header.clientWidth;
    const emptyBodyClientWidth = body.clientWidth;
    body.append(...retainedRows);
    const verticalHeaderBounds = header.getBoundingClientRect();
    const verticalBodyBounds = body.getBoundingClientRect();
    const verticalRow = renderedRows[0];
    const verticalHeaderLefts = headerCells.map((cell) =>
      Number(cell.getBoundingClientRect().left.toFixed(3)));
    const verticalBodyLefts = [...verticalRow.children].map((cell) =>
      Number(cell.getBoundingClientRect().left.toFixed(3)));
    const verticalBodyOverflows = body.scrollHeight > body.clientHeight;
    const verticalColumnsAlign = verticalHeaderLefts.every((left, index) =>
      Math.abs(left - verticalBodyLefts[index]) <= 0.5);
    const verticalBodyBelowHeader = verticalBodyBounds.top
      >= verticalHeaderBounds.bottom - 0.5;
    const verticalHeaderClientWidth = header.clientWidth;
    const verticalBodyClientWidth = body.clientWidth;
    const outerScrollStart = list.scrollLeft;
    const scrollHeaderStart = headerCells[0].getBoundingClientRect().left;
    const scrollBodyStart = verticalRow.children[0].getBoundingClientRect().left;
    list.scrollLeft = Math.min(48, list.scrollWidth - list.clientWidth);
    const outerScrollAmount = list.scrollLeft - outerScrollStart;
    const scrollHeaderDelta = headerCells[0].getBoundingClientRect().left
      - scrollHeaderStart;
    const scrollBodyDelta = verticalRow.children[0].getBoundingClientRect().left
      - scrollBodyStart;
    const innerHorizontalScrollLefts = [header.scrollLeft, body.scrollLeft];
    list.scrollLeft = list.scrollWidth;
    const maxScrollHeaderRight = headerCells.at(-1).getBoundingClientRect().right;
    const maxScrollBodyRight = verticalRow.lastElementChild
      .getBoundingClientRect().right;
    const maxScrollViewportRight = list.getBoundingClientRect().right;
    const maxScrollHeaderContentRight = header.getBoundingClientRect().left
      + header.clientWidth;
    const maxScrollBodyContentRight = body.getBoundingClientRect().left
      + body.clientWidth;
    list.scrollLeft = outerScrollStart;
    grid.style.removeProperty("block-size");
    const resizerElements = [...header.querySelectorAll(
      ".nami-file-list__column-resizer",
    )];
    const evidence = {
      table_role: list.getAttribute("role"),
      header_role: header.getAttribute("role"),
      body_role: body.getAttribute("role"),
      gallery_uses_work_area: galleryUsesWorkArea,
      gallery_fills_work_area: fillsWorkArea,
      collapse_hides_children: collapseHidesChildren,
      collapse_restores_children: collapseRestoresChildren,
      child_selection_selects_folder: childSelectionSelectsFolder,
      child_selection_restores_mixed: childSelectionRestoresMixed,
      master_initially_mixed: masterInitiallyMixed,
      master_selects_all: masterSelectsAll,
      master_deselects_all: masterDeselectsAll,
      master_label: masterCheckbox.getAttribute("aria-label"),
      resize_handle_count: resizerElements.length,
      resize_handle_columns: resizerElements.map(
        (resizer) => resizer.dataset.column,
      ),
      resize_handle_roles: resizerElements.map(
        (resizer) => resizer.getAttribute("role"),
      ),
      resize_handle_labels: resizerElements.map(
        (resizer) => resizer.getAttribute("aria-label"),
      ),
      notes_resizer_absent: header.querySelector(
        '.nami-file-list__column-resizer[data-column="notes"]',
      ) === null,
      initial_layout_frozen: initialLayoutFrozen,
      normal_columns_align: normalColumnsAlign,
      initial_column_widths: initialGeometry.widths,
      initial_column_lefts: initialGeometry.lefts,
      initial_right: initialGeometry.right,
      frozen_column_widths: frozenGeometry.widths,
      frozen_column_lefts: frozenGeometry.lefts,
      frozen_right: frozenGeometry.right,
      frozen_layout_active: grid.dataset.columnsFrozen === "true",
      pointer_column_widths: pointerGeometry.widths,
      pointer_column_lefts: pointerGeometry.lefts,
      pointer_right: pointerGeometry.right,
      column_resize_changes_width: columnResizeChangesWidth,
      resized_columns_align: resizedColumnsAlign,
      requested_pointer_delta: requestedPointerDelta,
      column_resize_delta: Number(resizeDelta.toFixed(3)),
      column_notes_delta: Number(notesResizeDelta.toFixed(3)),
      keyboard_column_widths: keyboardGeometry.widths,
      keyboard_column_lefts: keyboardGeometry.lefts,
      keyboard_right: keyboardGeometry.right,
      keyboard_resize_delta: Number(keyboardResizeDelta.toFixed(3)),
      keyboard_notes_delta: Number(keyboardNotesDelta.toFixed(3)),
      viewport_resize_amount: Number(viewportResizeAmount.toFixed(3)),
      viewport_narrow_widths: viewportNarrowGeometry.widths,
      viewport_narrow_right: viewportNarrowGeometry.right,
      viewport_narrow_right_span: viewportNarrowGeometry.rightSpan,
      viewport_narrow_list_width: viewportNarrowGeometry.listWidth,
      narrow_columns_align: narrowColumnsAlign,
      viewport_restored_widths: viewportRestoredGeometry.widths,
      viewport_restored_right: viewportRestoredGeometry.right,
      notes_minimum_widths: notesMinimumGeometry.widths,
      name_minimum_widths: nameMinimumGeometry.widths,
      name_minimum: rootFontSize * 12,
      notes_minimum: rootFontSize * 14,
      constrained_column_widths: constrainedGeometry.widths,
      constrained_grid_width: constrainedGeometry.gridWidth,
      constrained_right_span: constrainedGeometry.right
        - list.getBoundingClientRect().left,
      constrained_columns_align: constrainedColumnsAlign,
      header_foreground: headerStyle.color,
      header_background: headerStyle.backgroundColor,
      header_texts: headerCells.map((cell) => cell.textContent),
      header_cell_roles: headerCells.map((cell) => cell.getAttribute("role")),
      selection_header_label: headerCells[0].getAttribute("aria-label"),
      column_count: headerCells.length,
      row_count: rows.length,
      body_child_count: body.children.length,
      checkbox_count: body.querySelectorAll('.nami-checkbox[type="checkbox"]').length,
      body_ends_at_last_row: Math.abs(
        bodyBounds.bottom - lastRow.getBoundingClientRect().bottom,
      ) < 0.5,
      body_height_matches_rows: Math.abs(bodyBounds.height - rowsHeight) < 0.5,
      vertical_body_overflows: verticalBodyOverflows,
      vertical_columns_align: verticalColumnsAlign,
      vertical_body_below_header: verticalBodyBelowHeader,
      vertical_header_client_width: verticalHeaderClientWidth,
      vertical_body_client_width: verticalBodyClientWidth,
      header_inline_gutter_width: header.offsetWidth - header.clientWidth,
      body_inline_gutter_width: body.offsetWidth - body.clientWidth,
      empty_header_client_width: emptyHeaderClientWidth,
      empty_body_client_width: emptyBodyClientWidth,
      header_scrollbar_width: headerScrollbarStyle.width,
      body_scrollbar_width: bodyScrollbarStyle.width,
      header_scrollbar_gutter: headerStyle.scrollbarGutter,
      body_scrollbar_gutter: bodyStyle.scrollbarGutter,
      outer_scroll_amount: outerScrollAmount,
      scroll_header_delta: scrollHeaderDelta,
      scroll_body_delta: scrollBodyDelta,
      inner_horizontal_scroll_lefts: innerHorizontalScrollLefts,
      max_scroll_header_right: maxScrollHeaderRight,
      max_scroll_body_right: maxScrollBodyRight,
      max_scroll_viewport_right: maxScrollViewportRight,
      max_scroll_header_content_right: maxScrollHeaderContentRight,
      max_scroll_body_content_right: maxScrollBodyContentRight,
      horizontal_overflow: list.scrollWidth > list.clientWidth,
      overflow_x: getComputedStyle(list).overflowX,
      client_width: list.clientWidth,
      scroll_width: list.scrollWidth,
      rows,
    };
    list.style.removeProperty("inline-size");
    planSection.style.removeProperty("inline-size");
    return evidence;
  }

  const planEvidence = collectFileListEvidence(planSpecimen, PLAN_ROW_CASES);
  const integrityEvidence = collectFileListEvidence(
    integritySpecimen,
    INTEGRITY_ROW_CASES,
  );

  galleryMeasurementStep = "icon_registry";
  galleryFailureReason = "icon_invariant";
  const systemColors = {};
  for (const name of [
    "Canvas",
    "CanvasText",
    "Highlight",
    "HighlightText",
    "GrayText",
    "LinkText",
    "ButtonText",
  ]) {
    const probe = document.createElement("span");
    probe.style.color = name;
    app.append(probe);
    systemColors[name] = getComputedStyle(probe).color;
    probe.remove();
  }
  const buttonBorderProbe = document.createElement("span");
  buttonBorderProbe.style.border = "1px solid ButtonBorder";
  app.append(buttonBorderProbe);
  systemColors.ButtonBorder = getComputedStyle(buttonBorderProbe).borderColor;
  buttonBorderProbe.remove();
  const sizeIcons = ["sm", "md", "lg"].map((size) => {
    const glyph = icon("info", size);
    app.append(glyph);
    const style = getComputedStyle(glyph);
    return { size, width: style.width, height: style.height };
  });
  const inventory = document.createElement("section");
  inventory.className = "nami-card";
  const inventoryTitle = document.createElement("h2");
  inventoryTitle.textContent = "Icon inventory — 16, 20, 24 px";
  inventory.append(inventoryTitle);
  const inventoryIcons = [];
  for (const name of ICON_NAMES) {
    const row = document.createElement("p");
    const label = document.createElement("span");
    label.textContent = `${name} `;
    row.append(label);
    for (const size of ["sm", "md", "lg"]) {
      const glyph = icon(name, size);
      row.append(glyph);
      inventoryIcons.push({ name, size, glyph });
    }
    inventory.append(row);
  }
  app.append(inventory);
  const galleryIcons = [...document.querySelectorAll(".nami-icon")];
  const stateSamples = CONTROL_STATES.map(({ key: state }) => {
    const control = document.querySelector(`#gallery-control-button-${state}`);
    const glyph = control?.querySelector(".nami-icon--info");
    if (!(control instanceof HTMLElement) || !(glyph instanceof HTMLElement)) {
      throw new TypeError("button icon state specimen is unavailable");
    }
    const controlColor = getComputedStyle(control).color;
    const iconColor = getComputedStyle(glyph).backgroundColor;
    return {
      state,
      icon_color: iconColor,
      control_color: controlColor,
      control_background: getComputedStyle(control).backgroundColor,
      inherits: iconColor === controlColor,
    };
  });
  const maskImages = Object.fromEntries(inventoryIcons.map(({ name, size, glyph }) =>
    [`${name}:${size}`, getComputedStyle(glyph).maskImage],
  ));
  const maskLoads = {};
  const decodedMasks = new Set();
  // Check each asset once, sequentially: this is decode evidence, not a burst
  // load test of the local asset server. Every glyph/size mapping is retained.
  for (const [key, value] of Object.entries(maskImages)) {
    const match = /^url\(["']?([^"')]+)["']?\)$/.exec(value);
    if (match === null) throw new Error(`Invalid icon mask: ${key}: ${value}`);
    const url = new URL(match[1], document.baseURI);
    if (url.origin !== location.origin || !url.pathname.startsWith("/icons/")) {
      throw new Error(`Nonlocal icon mask: ${key}: ${url.href}`);
    }
    if (!decodedMasks.has(url.href)) {
      const result = await new Promise((resolve) => {
        const image = new Image();
        const finish = (event) => resolve({
          event, width: image.naturalWidth, height: image.naturalHeight,
        });
        image.onload = () => finish("load");
        image.onerror = () => finish("error");
        image.src = url.href;
      });
      if (result.event !== "load" || result.width <= 0 || result.height <= 0) {
        throw new Error(`Icon decode failed: ${JSON.stringify({
          key, url: url.href, ...result,
          resources: performance.getEntriesByName(url.href).map((entry) => entry.toJSON()),
        })}`);
      }
      decodedMasks.add(url.href);
    }
    maskLoads[key] = true;
  }
  const iconEvidence = {
    registry_frozen: Object.isFrozen(ICON_NAMES),
    registry_names: [...ICON_NAMES],
    all_registry_created: ICON_NAMES.every((name) =>
      galleryIcons.some((glyph) => glyph.classList.contains(`nami-icon--${name}`)),
    ),
    all_current_color: galleryIcons.every((glyph) => {
      const style = getComputedStyle(glyph);
      return style.backgroundColor === style.color;
    }),
    all_mask_images: galleryIcons.every((glyph) => {
      const value = getComputedStyle(glyph).maskImage;
      const match = /^url\(["']?([^"')]+)["']?\)$/.exec(value);
      if (match === null || match[1].startsWith("data:")) {
        return false;
      }
      const resolved = new URL(match[1], document.baseURI);
      return resolved.origin === location.origin && resolved.pathname.startsWith("/icons/");
    }),
    unexpected_svg_count: app.querySelectorAll("svg").length,
    unexpected_path_count: app.querySelectorAll("path").length,
    sizes: sizeIcons,
    state_samples: stateSamples,
    mask_images: maskImages,
    mask_loads: maskLoads,
    system_colors: systemColors,
  };
  const mixedStyle = getComputedStyle(mixedCheckbox, "::after");
  const mixedCheckboxStyle = getComputedStyle(mixedCheckbox);
  const uncheckedCheckboxStyle = getComputedStyle(uncheckedCheckbox);
  galleryMeasurementStep = "dialog_exit";
  galleryFailureReason = "dialog_invariant";
  const dialogExit = await dialogExitEvidence();
  galleryMeasurementStep = "confirmation_preview";
  galleryFailureReason = "dialog_invariant";
  const confirmationPreviewEvidence = await measureConfirmationPreview();
  themeTrigger.blur();
  themeTrigger.click();
  await new Promise((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const themePopup = document.querySelector("#theme-options");
  const selectedThemeOption = themePopup?.querySelector(
    '.nami-combobox__option[aria-selected="true"]',
  );
  galleryMeasurementStep = "combobox_layout";
  galleryFailureReason = "combobox_invariant";
  const selectionPill = selectedThemeOption?.querySelector(
    ".nami-combobox__selection",
  );
  if (
    !(themePopup instanceof HTMLElement)
    || !(selectedThemeOption instanceof HTMLElement)
    || !(hoveredThemeOption instanceof HTMLElement)
    || !(pressedThemeOption instanceof HTMLElement)
    || !(selectionPill instanceof HTMLElement)
    || themePopup.hidden
  ) {
    throw new TypeError("production combobox popup evidence is unavailable");
  }
  const triggerBounds = themeTrigger.getBoundingClientRect();
  const popupBounds = themePopup.getBoundingClientRect();
  const selectedBounds = selectedThemeOption.getBoundingClientRect();
  const triggerStyle = getComputedStyle(themeTrigger);
  const popupStyle = getComputedStyle(themePopup);
  galleryMeasurementStep = "task_rail_layout";
  galleryFailureReason = "task_rail_invariant";
  const taskCards = [...galleryRail.element.querySelectorAll(".nami-task-card")];
  for (const card of galleryRail.element.querySelectorAll(".nami-task-rail__row .nami-task-card")) {
    if (getComputedStyle(card.querySelector(".nami-task-card__paths")).color !== tertiaryColor) {
      throw new Error("task paths must use tertiary text");
    }
    for (const field of card.querySelectorAll(".nami-task-card__status, .nami-task-card__paths, .nami-task-card__progress")) {
      if (Math.abs(card.getBoundingClientRect().right - field.getBoundingClientRect().right - 18) > 0.5) {
        throw new Error("task detail endpoint must be inset 18px");
      }
    }
    const values = [...card.querySelectorAll(".nami-labeled-path__value")];
    if (values.length !== 2 || Math.abs(values[0].getBoundingClientRect().left - values[1].getBoundingClientRect().left) > 0.5) {
      throw new Error("task rail path starts must align");
    }
  }
  const selectedTaskCard = galleryRail.element.querySelector(
    '.nami-task-card[aria-selected="true"]',
  );
  const currentTaskCard = galleryRail.element.querySelector(
    '.nami-task-card[aria-current="page"]',
  );
  if (
    !(selectedTaskCard instanceof HTMLElement)
    || !(currentTaskCard instanceof HTMLElement)
  ) {
    throw new TypeError("gallery selected task specimens are unavailable");
  }
  const taskRailBounds = galleryRail.element.getBoundingClientRect();
  const planBounds = planSection.getBoundingClientRect();
  const accentTokens = Object.fromEntries([
    ["fill", "--color-accent-fill"],
    ["fill_hover", "--color-accent-fill-hover"],
    ["fill_pressed", "--color-accent-fill-pressed"],
    ["foreground", "--color-accent-fill-foreground"],
  ].map(([name, token]) => {
    const probe = document.createElement("span");
    probe.style.backgroundColor = `var(${token})`;
    probe.style.position = "fixed";
    probe.style.visibility = "hidden";
    app.append(probe);
    const resolved = getComputedStyle(probe).backgroundColor;
    probe.remove();
    return [name, resolved];
  }));
  galleryMeasurementStep = "native_minimum_request";
  galleryFailureReason = "native_minimum_pending";
  await dispatchInteractive(
    "test_report",
    Object.freeze({ phase: "minimum_window" }),
    validAccepted,
  );
  let nativeMinimum = null;
  for (let frame = 0; frame < 300; frame += 1) {
    nativeMinimum = await dispatchInteractive(
      "test_report",
      Object.freeze({ phase: "minimum_window_status" }),
      validMinimumWindowStatus,
    );
    if (minimumWindowSettled(
      nativeMinimum, window.innerWidth, window.innerHeight,
    )) break;
    if (frame === 299) throw new Error("native minimum window did not settle");
    await new Promise((resolve) => requestAnimationFrame(resolve));
  }
  if (nativeMinimum === null || nativeMinimum.complete !== true
      || Math.abs(nativeMinimum.minimum_width - 1024 * nativeMinimum.owner_scale) > 1
      || Math.abs(nativeMinimum.minimum_height
        - minimumNativeWindowHeight * nativeMinimum.owner_scale) > 1) {
    galleryFailureReason = "native_minimum_dimensions";
    throw new Error("native minimum window completion is invalid");
  }
  galleryMeasurementStep = "native_minimum_layout";
  galleryFailureReason = "layout_invariant";
  const catalogNodes = [...app.children];
  const catalogRootStyle = {
    blockSize: app.style.blockSize,
    gridTemplateRows: app.style.gridTemplateRows,
    overflow: app.style.overflow,
  };
  const catalogPanelStyle = {
    blockSize: planReviewPanel.element.style.blockSize,
    gridColumn: planReviewPanel.element.style.gridColumn,
  };
  const catalogStash = document.createDocumentFragment();
  catalogStash.append(...catalogNodes);
  app.style.removeProperty("block-size");
  app.style.removeProperty("grid-template-rows");
  app.style.removeProperty("overflow");
  const minimumHeader = document.createElement("header");
  minimumHeader.className = "nami-shell__header";
  const minimumHeading = document.createElement("h1");
  const minimumStatus = document.createElement("p");
  minimumStatus.id = "host-status";
  renderText(minimumHeading, "NamiSync");
  renderText(minimumStatus, "Execution review");
  minimumHeader.append(minimumHeading, minimumStatus);
  const minimumRail = galleryRail.element;
  const minimumWork = document.createElement("main");
  minimumWork.className = "nami-work-panel";
  const minimumWorkBody = document.createElement("div");
  minimumWorkBody.className = "nami-work-panel__body";
  minimumWork.append(minimumWorkBody);
  planReviewPanel.element.style.removeProperty("block-size");
  planReviewPanel.element.style.removeProperty("grid-column");
  minimumWorkBody.append(planReviewPanel.element);
  app.append(minimumHeader, minimumRail, minimumWork);
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const minimumLayoutEvidence = [
    await diagnosticLayout("minimum-folded-empty", null, false, false),
    await diagnosticLayout("minimum-folded-populated", null, false, true),
    await diagnosticLayout("minimum-expanded-empty", null, true, false),
    await diagnosticLayout("minimum-expanded-populated", null, true, true),
  ];
  diagnosticLayoutEvidence.push(...minimumLayoutEvidence);
  const minimumFilterTrigger = planReviewPanel.element.querySelector('[data-action="filter-menu"]');
  const minimumFilterPopup = planReviewPanel.element.querySelector('.nami-filter-menu__popup');
  minimumFilterTrigger.click();
  minimumFilterPopup.dispatchEvent(new KeyboardEvent('keydown', {key:'Home', bubbles:true}));
  await new Promise(resolve => requestAnimationFrame(resolve));
  const firstFilter = minimumFilterPopup.querySelector('[data-filter="all"]');
  const firstFilterBounds = firstFilter.getBoundingClientRect();
  const firstFilterHit = document.elementFromPoint((firstFilterBounds.left + firstFilterBounds.right) / 2,
    (firstFilterBounds.top + firstFilterBounds.bottom) / 2);
  minimumFilterPopup.dispatchEvent(new KeyboardEvent('keydown', {key:'End', bubbles:true}));
  await new Promise(resolve => requestAnimationFrame(resolve));
  const finalFilter = minimumFilterPopup.querySelector('[data-filter="notice"]');
  const menuBounds = minimumFilterPopup.getBoundingClientRect();
  const finalFilterBounds = finalFilter.getBoundingClientRect();
  const clipBounds = minimumWork.getBoundingClientRect();
  const finalFilterHit = document.elementFromPoint((finalFilterBounds.left + finalFilterBounds.right) / 2,
    (finalFilterBounds.top + finalFilterBounds.bottom) / 2);
  const filterMenuGeometry = {
    accent_pair: filterAccentPair, neutral_pair: filterNeutralPair,
    active_fill: activeFilterFill, inactive_fill: inactiveFilterFill,
    popup_inside: menuBounds.top >= clipBounds.top && menuBounds.bottom <= clipBounds.bottom
      && menuBounds.left >= clipBounds.left && menuBounds.right <= clipBounds.right,
    first_reachable: firstFilterBounds.top >= menuBounds.top && firstFilterBounds.bottom <= menuBounds.bottom
      && firstFilter.contains(firstFilterHit),
    end_reachable: document.activeElement === finalFilter && finalFilterBounds.top >= menuBounds.top
      && finalFilterBounds.bottom <= menuBounds.bottom && finalFilter.contains(finalFilterHit),
    rectangles: [rectangle(minimumFilterTrigger), rectangle(minimumFilterPopup), rectangle(minimumWork),
      [firstFilterBounds.left, firstFilterBounds.top, firstFilterBounds.right, firstFilterBounds.bottom]
        .map(value => Math.round(value * 1000) / 1000), rectangle(finalFilter)],
  };
  minimumFilterPopup.dispatchEvent(new Event('scroll'));
  filterMenuGeometry.internal_scroll_preserved = !minimumFilterPopup.hidden;
  window.dispatchEvent(new Event('resize'));
  filterMenuGeometry.resize_closed = minimumFilterPopup.hidden;
  if (!minimumFilterPopup.hidden) minimumFilterTrigger.click();
  minimumFilterTrigger.click();
  minimumWorkBody.dispatchEvent(new Event('scroll'));
  filterMenuGeometry.outside_scroll_closed = minimumFilterPopup.hidden;
  if (!minimumFilterPopup.hidden) minimumFilterTrigger.click();
  const minimumAllDiagnostics = minimumLayoutEvidence.at(-1);
  if (minimumAllDiagnostics === undefined) throw new Error("native minimum A1 evidence is missing");
  galleryMeasurementStep = "native_minimum_keyboard";
  galleryFailureReason = "layout_invariant";
  globalThis.__namiGalleryA1Keyboard = null;
  await dispatchInteractive(
    "test_report",
    Object.freeze({ phase: "a1_keyboard" }),
    validAccepted,
  );
  let nativeKeyboard = null;
  for (let frame = 0; frame < 300; frame += 1) {
    nativeKeyboard = globalThis.__namiGalleryA1Keyboard;
    if (nativeKeyboard !== null) break;
    if (frame === 299) throw new Error("native minimum keyboard evidence did not complete");
    await new Promise((resolve) => requestAnimationFrame(resolve));
  }
  if (!(Number.isFinite(nativeKeyboard?.before)
      && Number.isFinite(nativeKeyboard?.after)
      && nativeKeyboard.after > nativeKeyboard.before
      && nativeKeyboard.capture === true
      && Array.isArray(nativeKeyboard.dimensions)
      && nativeKeyboard.dimensions.length === 2
      && nativeKeyboard.dimensions.every((value) => Number.isInteger(value) && value > 0))) {
    throw new Error("native minimum keyboard or capture evidence is invalid");
  }
  const minimumWorkBounds = minimumWork.getBoundingClientRect();
  const minimumWorkContentBounds = minimumWorkBody.getBoundingClientRect();
  const minimumRootBounds = planReviewPanel.element.getBoundingClientRect();
  galleryMeasurementStep = "execution_axes";
  galleryFailureReason = "execution_axes_invariant";
  const executionAxes = planReviewPanel.element.querySelector(".nami-plan-review__execution-axes");
  if (!(executionAxes instanceof HTMLElement)) {
    throw new TypeError("native minimum execution axes are unavailable");
  }
  const axesLineHeight = parseFloat(getComputedStyle(executionAxes).lineHeight);
  minimumWindowEvidence = {
    filter_menu: filterMenuGeometry,
    default_outer_width: defaultWindowSize.outer_width,
    default_outer_height: defaultWindowSize.outer_height,
    native_default_owner_scale: nativeDefault.owner_scale,
    native_default_outer_width: nativeDefault.outer_width,
    native_default_outer_height: nativeDefault.outer_height,
    outer_width: window.outerWidth,
    outer_height: window.outerHeight,
    inner_width: window.innerWidth,
    inner_height: window.innerHeight,
    native_owner_scale: nativeMinimum.owner_scale,
    native_minimum_width: nativeMinimum.minimum_width,
    native_minimum_height: nativeMinimum.minimum_height,
    native_outer_width: nativeMinimum.outer_width,
    native_outer_height: nativeMinimum.outer_height,
    native_client_width: nativeMinimum.client_width,
    native_client_height: nativeMinimum.client_height,
    work_width: Number(minimumWorkBounds.width.toFixed(3)),
    work_content_width: Number(minimumWorkContentBounds.width.toFixed(3)),
    work_content_aligned: Math.abs(minimumRootBounds.left - minimumWorkContentBounds.left) <= 1
      && Math.abs(minimumRootBounds.right - minimumWorkContentBounds.right) <= 1,
    work_height: Number(minimumWorkBounds.height.toFixed(3)),
    review_width: Number(minimumRootBounds.width.toFixed(3)),
    review_height: Number(minimumRootBounds.height.toFixed(3)),
    axes_wrapped: executionAxes.scrollHeight > axesLineHeight + 1,
    long_trash_length: longTrashLocation.length,
    keyboard_scroll_before: nativeKeyboard.before,
    keyboard_scroll_after: nativeKeyboard.after,
    keyboard_capture_width: nativeKeyboard.dimensions[0],
    keyboard_capture_height: nativeKeyboard.dimensions[1],
  };
  app.replaceChildren(...catalogNodes);
  app.style.blockSize = catalogRootStyle.blockSize;
  app.style.gridTemplateRows = catalogRootStyle.gridTemplateRows;
  app.style.overflow = catalogRootStyle.overflow;
  planReviewPanel.element.style.blockSize = catalogPanelStyle.blockSize;
  planReviewPanel.element.style.gridColumn = catalogPanelStyle.gridColumn;
  galleryMeasurementStep = "recent_ui_specimens";
  galleryFailureReason = "layout_invariant";
  // These panels remain in the manual gallery after the measurement matrix.
  const recentSection = document.createElement("section");
  recentSection.dataset.gallerySection = "recent_ui";
  recentSection.style.gridColumn = "1 / -1";
  const recentHeading = document.createElement("h2");
  renderText(recentHeading, "Execution refusals, prior moves and controls");
  recentSection.append(recentHeading);
  app.append(recentSection);
  const recentPanels = [];
  function recentPanel(label, task, overrides = {}) {
    const heading = document.createElement("h3");
    renderText(heading, label);
    const callbacks = Object.fromEntries(Object.keys(planReviewCallbacks).map((name) => [name, () => {}]));
    const panel = createPlanReviewPanel({ ...callbacks, ...overrides });
    panel.element.style.blockSize = "480px";
    panel.element.style.inlineSize = "min(100%, 48rem)";
    panel.render(task);
    recentSection.append(heading, panel.element);
    recentPanels.push(panel.element);
    return panel;
  }
  function recentTask(rows = []) {
    return {
      ...planReviewTask, taskId: "gallery-recent", sessionId: "6".repeat(32),
      reviewSessionId: "6".repeat(32),
      review: {
        ...planReviewTask.review, message: "",
        summary: { ...planReviewTask.review.summary, filters: [], highlight_focus_node_id: null },
        window: { ...planReviewTask.review.window, total: rows.length, rows },
      },
    };
  }
  // Display-ready messages mirror the app's fixed guidance; no refusal policy runs here.
  const refusalCases = [
    { origin: "preflight", codes: ["insufficient_space", "source_drift"], message: "Execution preflight refused. The target has insufficient free space. Free space on its drive. A source item changed after review. Resolve these issues, then click Plan again." },
    { origin: "commitment", codes: [], message: "Execution commitment is invalid. Click Plan again and review the new plan before executing." },
    { origin: "other", codes: [], message: "Execution was refused before it started. Click Plan again and review the new plan." },
  ];
  const refusalEvidence = refusalCases.map((fixture) => {
    const task = recentTask();
    task.executionStarted = true;
    task.sessionState = "refused";
    task.review.summary.selection_state = "committed";
    task.review.message = fixture.message;
    task.review.window.execution = {
      ...task.review.window.execution, session_id: task.sessionId,
      result: { ...calmExecutionResult, headline: "refused", filesystem: "refused", disposition: "unrun" },
      refusal: { origin: fixture.origin, codes: fixture.codes },
    };
    const panel = recentPanel(`${fixture.origin} refusal`, task);
    return {
      origin: task.review.window.execution.refusal.origin,
      codes: task.review.window.execution.refusal.codes,
      message: panel.element.querySelector(".nami-plan-review__status").textContent,
      title: panel.element.querySelector(".nami-plan-review__status-title").textContent,
    };
  });
  const priorRow = {
    ...planReviewTask.review.window.rows[0], display: `1 item moved to ${galleryMoveDisplay}`,
    expanded: false, position_in_set: 1, set_size: 3,
    move_group: { count: 1, destination_display: galleryMoveDisplay },
  };
  const destinationRow = {
    ...priorRow, node_id: priorRow.move_peer_id, display: galleryMovePath.split("\\").at(-1),
    row_kind: "folder", expanded: true, move_peer_id: null, move_group: null,
    position_in_set: 2, size: "4096", selection: "selected",
    selectable_operation_count: 1, selected_operation_count: 1, operation_count: 1,
  };
  const priorChild = {
    ...priorRow, node_id: `node-${"a".repeat(32)}`, display: "old-report.pdf",
    operation_kind: "move", presentation_kind: "move", row_kind: "prior-operation", depth: 1, is_container: false,
    operation_count: 1, reason: "identity_rename",
    move_peer_id: `node-${"b".repeat(32)}`, move_group: null,
    parent_visible_index: 0, position_in_set: 1, set_size: 1,
  };
  const canonicalRow = {
    ...priorChild, node_id: priorChild.move_peer_id, display: "report.pdf",
    row_kind: "operation", operation_id: "5".repeat(32), move_peer_id: priorChild.node_id,
    prior_name: null,
    selection: "selected", selectable_operation_count: 1,
    selected_operation_count: 1, operation_count: 1, size: "4096", mtime_ns: "1000000000",
    execution: { operation: null, automatic_verification: null, evidence: null },
  };
  const renamedRow = {
    ...canonicalRow, node_id: `node-${"c".repeat(32)}`, operation_id: "6".repeat(32),
    display: "Logo.PNG", operation_kind: "recase", presentation_kind: "rename",
    prior_name: "logo.png", move_peer_id: null, depth: 0, parent_visible_index: null,
    position_in_set: 3, set_size: 3,
  };
  const moveTask = recentTask();
  moveTask.review.summary.selected_operation_count = 2;
  moveTask.review.summary.selectable_operation_count = 2;
  moveTask.review.summary.scope_selected_operation_count = 2;
  moveTask.review.summary.scope_selectable_operation_count = 2;
  moveTask.review.summary.required_bytes = "8192";
  moveTask.review.summary.filter_counts = {
    all: 2, copy: 0, mkdir: 0, move: 1, rename: 1, update: 0, move_update: 0,
    trash: 0, delete: 0, noop: 0, error: 0, unsupported: 0, blocked: 0, notice: 0,
  };
  let revealedNode = null;
  function renderMoveRows(expanded, revealed) {
    const destinationIndex = expanded ? 2 : 1;
    const rows = [
      { ...priorRow, expanded, first_child_visible_index: expanded ? 1 : null },
      ...(expanded ? [priorChild] : []),
      { ...destinationRow, highlighted: revealed, first_child_visible_index: destinationIndex + 1 },
      { ...canonicalRow, parent_visible_index: destinationIndex },
      renamedRow,
    ].map((row, index) => ({ ...row, visible_index: index }));
    moveTask.review.window = { ...moveTask.review.window, rows, total: rows.length };
    moveTask.review.summary.highlight_focus_node_id = revealed ? destinationRow.node_id : null;
    moveTask.review.summary.highlight_revision = (moveTask.review.summary.highlight_revision ?? 0) + 1;
    movePanel.render(moveTask);
  }
  const movePanel = recentPanel("Prior location — reveal destination preview", moveTask, {
    onRevealMove: (review, nodeId) => {
      revealedNode = nodeId;
      review.message = `Gallery preview: destination ${galleryMovePath} revealed. No files were changed.`;
      renderMoveRows(review.window.rows[0].expanded, true);
    },
    onViewChange: (review, patch) => {
      const expanded = patch.collapsed !== true;
      renderMoveRows(expanded, revealedNode !== null);
    },
  });
  renderMoveRows(false, false);
  const movePill = movePanel.element.querySelector(".nami-plan-move-pill");
  const initialCollapsed = movePanel.element.querySelector(".nami-file-row__disclosure").ariaExpanded === "false";
  movePill.click();
  movePanel.element.querySelector(".nami-file-row__disclosure").click();
  const livePill = movePanel.element.querySelector(".nami-plan-move-pill");
  const liveBadge = livePill.querySelector(".nami-badge");
  const livePath = livePill.querySelector(".nami-plan-move-pill__destination");
  const movedAnnotation = movePanel.element.querySelector(`[data-node-id="${canonicalRow.node_id}"] .nami-plan-row__previous`);
  const renamedAnnotation = movePanel.element.querySelector(`[data-node-id="${renamedRow.node_id}"] .nami-plan-row__previous`);
  const actionStyle = getComputedStyle(movePanel.element.querySelector(".nami-file-state-label"));
  const moveEvidence = {
    destination: movePill.querySelector(".nami-plan-move-pill__destination").textContent,
    title: movePill.title, revealed_node: revealedNode,
    expanded: movePanel.element.querySelector(".nami-file-row__disclosure").ariaExpanded,
    checkable: movePanel.element.querySelector(`[data-node-id="${priorRow.node_id}"] .nami-checkbox`) !== null,
    prior_child_visible: movePanel.element.querySelector(`[data-node-id="${priorChild.node_id}"]`) !== null,
    destination_highlighted: movePanel.element.querySelector(`[data-node-id="${destinationRow.node_id}"]`).ariaSelected,
    revealed_destination: destinationRow.node_id,
    prior_action: movePanel.element.querySelector(`[data-node-id="${priorChild.node_id}"] .nami-plan-row__intent`).textContent,
    prior_metadata: movePanel.element.querySelector(`[data-node-id="${priorChild.node_id}"] .nami-file-row__size`).textContent
      + movePanel.element.querySelector(`[data-node-id="${priorChild.node_id}"] .nami-plan-row__modified`).textContent,
    prior_selection_disabled: movePanel.element.querySelector(`[data-node-id="${priorChild.node_id}"] .nami-checkbox`).disabled,
    initial_collapsed: initialCollapsed,
    path_in_badge: livePath.parentElement === liveBadge,
    badge_matches_action_radius: getComputedStyle(liveBadge).borderRadius === actionStyle.borderRadius,
    path_clipped: livePath.scrollWidth > livePath.clientWidth && getComputedStyle(livePath).textOverflow === "ellipsis",
    moved_annotation: movedAnnotation.textContent,
    renamed_annotation: renamedAnnotation.textContent,
    rename_action: movePanel.element.querySelector(`[data-node-id="${renamedRow.node_id}"] .nami-plan-row__intent`).textContent,
    annotations_purple: getComputedStyle(movedAnnotation).color === getComputedStyle(renamedAnnotation).color
      && getComputedStyle(renamedAnnotation).color === getComputedStyle(movePanel.element.querySelector(`[data-node-id="${renamedRow.node_id}"] .nami-file-state-label`)).color,
    hierarchy: moveTask.review.window.rows.map((row) => [row.visible_index, row.depth,
      row.parent_visible_index, row.first_child_visible_index, row.position_in_set, row.set_size]),
    row_indexes: [...movePanel.element.querySelectorAll("[data-node-id]")].map((row) => row.ariaRowIndex),
    message: movePanel.element.querySelector(".nami-plan-review__status").textContent,
  };
  const moveGrid = movePanel.element.querySelector(".nami-file-list__grid");
  const savedNameWidth = moveGrid.style.getPropertyValue("--nami-file-column-name");
  const savedPriorName = renamedRow.prior_name;
  moveGrid.style.setProperty("--nami-file-column-name", "320px");
  renamedRow.prior_name = `${"x".repeat(247)}logo.png`;
  renderMoveRows(true, true);
  const longOriginRow = movePanel.element.querySelector(`[data-node-id="${renamedRow.node_id}"]`);
  const longOrigin = longOriginRow.querySelector(".nami-plan-row__previous");
  const retainedFilename = longOriginRow.querySelector(".nami-file-row__name-text");
  moveEvidence.long_origin_keeps_filename = retainedFilename.clientWidth >= retainedFilename.scrollWidth;
  moveEvidence.long_origin_clipped = longOrigin.clientWidth < longOrigin.scrollWidth
    && getComputedStyle(longOrigin).textOverflow === "ellipsis";
  renamedRow.prior_name = savedPriorName;
  if (savedNameWidth === "") moveGrid.style.removeProperty("--nami-file-column-name");
  else moveGrid.style.setProperty("--nami-file-column-name", savedNameWidth);
  renderMoveRows(true, true);
  moveTask.review.message = "Click the move pill to preview revealing its destination. Expand the prior group independently.";
  movePanel.render(moveTask);
  const controlTask = recentTask();
  controlTask.executionStarted = true;
  controlTask.sessionState = "active";
  controlTask.review.summary.selection_state = "committed";
  controlTask.review.window.execution = { ...controlTask.review.window.execution, session_id: controlTask.sessionId };
  const localCommands = [];
  const controlPanel = recentPanel("Pause / Resume and two-click Cancel preview", controlTask, {
    onControl: (review, action) => {
      localCommands.push(action);
      controlTask.executionControlState = action === "pause" ? "paused" : "running";
      review.message = action === "cancel"
        ? "Gallery preview canceled. No files were changed; controls are ready to try again."
        : `Gallery preview ${action === "pause" ? "paused" : "resumed"}. No files were changed.`;
      controlPanel.render(controlTask);
    },
  });
  function actionSnapshot(action) {
    const button = controlPanel.element.querySelector(`[data-action="${action}"]`);
    const icon = [...button.querySelectorAll(".nami-icon")].find((glyph) => !glyph.hidden);
    return { label: button.textContent, primary: button.classList.contains("nami-button--primary"), disabled: button.disabled, mask: getComputedStyle(icon).maskImage };
  }
  const pauseStates = [actionSnapshot("pause")];
  controlPanel.element.querySelector('[data-action="pause"]').click();
  pauseStates.push(actionSnapshot("resume"));
  controlPanel.element.querySelector('[data-action="resume"]').click();
  controlTask.executionControlState = "pausing";
  controlPanel.render(controlTask);
  pauseStates.push(actionSnapshot("pause"));
  controlTask.executionControlState = "running";
  controlPanel.render(controlTask);
  const cancelStates = [actionSnapshot("cancel")];
  const cancelButton = controlPanel.element.querySelector('[data-action="cancel"]');
  cancelButton.click();
  cancelStates.push(actionSnapshot("cancel"));
  const commandsAfterArm = localCommands.length;
  cancelButton.click();
  cancelStates.push(actionSnapshot("cancel"));
  cancelButton.click();
  await new Promise((resolve) => setTimeout(resolve, 5050));
  cancelStates.push(actionSnapshot("cancel"));
  const recentUiEvidence = {
    refusals: refusalEvidence, move: moveEvidence, pause: pauseStates,
    cancel: cancelStates, commands_after_arm: commandsAfterArm,
    commands: [...localCommands], retained_panels: recentSection.querySelectorAll(".nami-plan-review").length,
  };
  localCommands.length = 0;
  controlTask.review.message = "Gallery preview only: Pause switches to Resume. Click Cancel twice within five seconds to preview cancellation.";
  controlPanel.render(controlTask);
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  function rectangle(element) {
    const bounds = element.getBoundingClientRect();
    return [bounds.left, bounds.top, bounds.right, bounds.bottom].map((value) => Number(value.toFixed(3)));
  }
  recentUiEvidence.layout = recentPanels.map((panel) => ({
    panel: rectangle(panel), status: rectangle(panel.querySelector(".nami-plan-review__status")),
    viewport: rectangle(panel.querySelector(".nami-plan-review__list")),
    horizontal_scroll: getComputedStyle(panel.querySelector(".nami-plan-review__list")).overflowX,
    controls: [...panel.querySelectorAll('[data-action="execute"], [data-action="plan-again"], [data-action="pause"], [data-action="resume"], [data-action="cancel"]')]
      .filter((control) => control.closest("[hidden]") === null).map(rectangle),
    rows: [...panel.querySelectorAll("[data-node-id]")].map(rectangle),
  }));
  const controlContract = {
    recent_ui: recentUiEvidence,
    accent: accentTokens,
    tri_state: {
      aria_checked: mixedCheckbox.getAttribute("aria-checked"),
      indeterminate: mixedCheckbox.indeterminate,
      cue_content: mixedStyle.content,
      unchecked_border: uncheckedCheckboxStyle.borderColor,
      unchecked_border_width: uncheckedCheckboxStyle.borderWidth,
      mixed_background: mixedCheckboxStyle.backgroundColor,
      mixed_foreground: mixedCheckboxStyle.color,
      mixed_border: mixedCheckboxStyle.borderColor,
      mixed_border_width: mixedCheckboxStyle.borderWidth,
      mixed_mask: mixedStyle.maskImage,
      mixed_size: `${mixedStyle.width} ${mixedStyle.height}`,
      checked_mask: getComputedStyle(checkedCheckbox, "::after").maskImage,
      checked_size: `${getComputedStyle(checkedCheckbox, "::after").width} ${getComputedStyle(checkedCheckbox, "::after").height}`,
    },
    dialog_exit: dialogExit,
    confirmation_preview: confirmationPreviewEvidence,
    diagnostic_layout: diagnosticLayoutEvidence,
    inventory_panel: inventoryPanelEvidence,
    minimum_window: minimumWindowEvidence,
    segmented: (() => {
      galleryMeasurementStep = "segmented_state";
      galleryFailureReason = "segmented_state_invariant";
      const selected = document.querySelector(
        "#gallery-control-segmented_control-rest",
      );
      const group = selected?.parentElement;
      const unselected = group?.querySelector(
        '.nami-segmented__item[aria-checked="false"]',
      );
      if (
        !(selected instanceof HTMLButtonElement)
        || !(group instanceof HTMLElement)
        || !(unselected instanceof HTMLButtonElement)
      ) {
        throw new TypeError("segmented state specimen is unavailable");
      }
      return {
        group_role: group.getAttribute("role"),
        selected_role: selected.getAttribute("role"),
        selected_checked: selected.getAttribute("aria-checked"),
        unselected_role: unselected.getAttribute("role"),
        unselected_checked: unselected.getAttribute("aria-checked"),
      };
    })(),
    combobox: {
      trigger_role: themeTrigger.getAttribute("role"),
      popup_role: themePopup.getAttribute("role"),
      expanded: themeTrigger.getAttribute("aria-expanded"),
      selected: selectedThemeOption.getAttribute("aria-selected"),
      option_count: themePopup.querySelectorAll(".nami-combobox__option").length,
      popup_width_delta: Number(
        Math.abs(popupBounds.width - triggerBounds.width).toFixed(3),
      ),
      popup_within_viewport: popupBounds.top >= 7.5
        && popupBounds.left >= 7.5
        && popupBounds.right <= window.innerWidth - 7.5
        && popupBounds.bottom <= window.innerHeight - 7.5,
      selected_center_error: Number(Math.abs(
        (selectedBounds.top + selectedBounds.height / 2)
        - (triggerBounds.top + triggerBounds.height / 2)
      ).toFixed(3)),
      placement_clamped: popupBounds.top <= 8.5
        || popupBounds.bottom >= window.innerHeight - 8.5,
      trigger_background_image: triggerStyle.backgroundImage,
      trigger_outline_style: triggerStyle.outlineStyle,
      popup_background: popupStyle.backgroundColor,
      popup_border: popupStyle.borderColor,
      popup_border_width: popupStyle.borderWidth,
      popup_shadow: popupStyle.boxShadow,
      popup_backdrop_filter: popupStyle.backdropFilter,
      ordinary_option_background: ordinaryOptionRestBackground,
      selected_option_background: getComputedStyle(
        selectedThemeOption,
      ).backgroundColor,
      hovered_option_background: getComputedStyle(
        hoveredThemeOption,
      ).backgroundColor,
      pressed_option_background: getComputedStyle(
        pressedThemeOption,
      ).backgroundColor,
      selected_pill_width: selectionPill.getBoundingClientRect().width,
      selected_pill_background: getComputedStyle(selectionPill).backgroundColor,
    },
    task_rail: {
      card_count: taskCards.length,
      outside_content_card: taskCards.every(
        (task) => task.closest(".nami-card") === null,
      ),
      left_of_work: taskRailBounds.right <= planBounds.left + 0.5,
      selected_count: galleryRail.element.querySelectorAll(
        '.nami-task-card[aria-selected="true"]',
      ).length,
      current_count: galleryRail.element.querySelectorAll(
        '.nami-task-card[aria-current="page"]',
      ).length,
      selected_current_same_card: selectedTaskCard === currentTaskCard,
      transparent_boundaries: taskCards.every((task) => {
        const style = getComputedStyle(task);
        return style.borderStyle === "none" || parseFloat(style.borderWidth) === 0;
      }),
      selected_marker_width: parseFloat(
        getComputedStyle(selectedTaskCard, "::before").width,
      ),
      selected_marker_height: parseFloat(
        getComputedStyle(selectedTaskCard, "::before").height,
      ),
      current_marker_width: parseFloat(
        getComputedStyle(currentTaskCard, "::before").width,
      ),
      current_marker_height: parseFloat(
        getComputedStyle(currentTaskCard, "::before").height,
      ),
      rest_marker_content: getComputedStyle(taskCards[1], "::before").content,
      selected_marker_background: getComputedStyle(
        selectedTaskCard,
        "::before",
      ).backgroundColor,
    },
    file_list: planEvidence,
    integrity_list: integrityEvidence,
  };

  optionStatePopup.remove();

  galleryStage = "report";
  galleryMeasurementStep = "report_assembly";
  galleryFailureReason = "report_invariant";
  const sectionBounds = [...app.querySelectorAll(":scope > [data-gallery-section]")]
    .map((section) => section.getBoundingClientRect());
  for (const [index, bounds] of sectionBounds.entries()) {
    if (sectionBounds.slice(index + 1).some((other) =>
      Math.min(bounds.right, other.right) - Math.max(bounds.left, other.left) > 1
      && Math.min(bounds.bottom, other.bottom) - Math.max(bounds.top, other.top) > 1)) {
      throw new Error("gallery specimen sections overlap");
    }
  }
  const reportParts = [
    { name: "lifecycles", value: lifecycles },
    { name: "intents", value: intents },
  ];
  for (let offset = 0; offset < controls.length; offset += CONTROL_REPORT_CHUNK_ROWS) {
    reportParts.push({
      name: "controls",
      value: controls.slice(offset, offset + CONTROL_REPORT_CHUNK_ROWS),
    });
  }
  reportParts.push(
    { name: "lifecycle_progress", value: lifecycleProgress },
    { name: "diagnostic_layout", value: controlContract.diagnostic_layout },
    { name: "inventory_panel", value: controlContract.inventory_panel },
    { name: "control_contract", value: Object.fromEntries(Object.entries(controlContract)
      .filter(([name]) => !["diagnostic_layout", "inventory_panel"].includes(name))) },
    {
      name: "motion",
      value: Object.freeze({
        nonessential_max_ms: nonessentialMax,
        indeterminate_iteration_count: indeterminateIterationCount,
      }),
    },
    { name: "icons", value: iconEvidence },
  );
  for (const [sequence, part] of reportParts.entries()) {
    await dispatchInteractive(
      "test_report",
      Object.freeze({
        phase: "part",
        sequence,
        name: part.name,
        value: part.value,
      }),
      validAccepted,
    );
  }
  await dispatchInteractive(
    "test_report",
    Object.freeze({
      phase: "complete",
      mode,
      media: Object.freeze({
        dark,
        forced,
        reduced,
        hdr: matchMedia("(dynamic-range: high)").matches,
        advanced_color: document.documentElement.dataset.advancedColor === "true",
      }),
      cosmetic: cosmeticEvidence,
      part_count: reportParts.length,
    }),
    validAccepted,
  );
  gallerySettled = true;
  if (galleryWatchdog !== null) clearTimeout(galleryWatchdog);
  renderText(status, `Gallery ${mode} complete`);

  async function dialogExitEvidence() {
    const dialog = document.createElement("dialog");
    dialog.className = "nami-dialog";
    renderText(dialog, "Dialog exit evidence");
    app.append(dialog);
    dialog.showModal();
    await new Promise((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const duration = durationMilliseconds(
      getComputedStyle(dialog).transitionDuration,
    );
    await new Promise((resolve) => setTimeout(resolve, duration + 50));
    const openOpacity = parseFloat(getComputedStyle(dialog).opacity);
    dialog.dataset.closing = "true";
    await new Promise((resolve) => setTimeout(resolve, duration + 50));
    const closingOpacity = parseFloat(getComputedStyle(dialog).opacity);
    const retainedWhileClosing = dialog.open;
    dialog.close();
    const closed = !dialog.open;
    dialog.remove();
    return {
      opened: openOpacity > 0.99,
      retained_while_closing: retainedWhileClosing,
      faded: closingOpacity < 0.01,
      closed,
    };
  }

  async function measureConfirmationPreview() {
    const dialog = confirmationPreview.element;
    const initiallyClosed = !dialog.open;
    async function waitForClose() {
      for (let frame = 0; frame < 120; frame += 1) {
        if (!dialog.open) return;
        await new Promise((resolve) => requestAnimationFrame(resolve));
      }
      throw new Error("gallery confirmation preview did not close");
    }
    previewButton.focus();
    previewButton.click();
    const openedFromButton = dialog.open && dialog.matches(":modal");
    const backgroundInert = app.inert && document.querySelector("#theme-options").inert;
    const scrollRoot = document.scrollingElement;
    const scrollableGallery = scrollRoot.scrollHeight > innerHeight + 100;
    const beforeWheel = scrollRoot.scrollTop;
    for (const target of ["content", "backdrop"]) {
      galleryFailureReason = "native_wheel_pending";
      globalThis.__namiGalleryWheelTarget = null;
      await dispatchInteractive(
        "test_report", Object.freeze({ phase: "preview_wheel", target }), validAccepted,
      );
      for (let frame = 0; globalThis.__namiGalleryWheelTarget !== target; frame += 1) {
        if (frame === 300) throw new Error("native gallery wheel input did not complete");
        await new Promise((resolve) => requestAnimationFrame(resolve));
      }
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    }
    galleryFailureReason = "dialog_invariant";
    const wheelBlocked = scrollableGallery && scrollRoot.scrollTop === beforeWheel;
    dialog.querySelector("[data-cancel-execution]").click();
    await waitForClose();
    const cancelClosed = !app.inert && !document.querySelector("#theme-options").inert
      && previewResult.textContent === "Preview canceled. No files were changed.";
    const cancelFocus = document.activeElement === previewButton;
    previewButton.click();
    dialog.querySelector("[data-confirm-execution]").click();
    await waitForClose();
    return {
      initially_closed: initiallyClosed,
      opened_from_button: openedFromButton,
      background_inert: backgroundInert,
      cancel_closed: cancelClosed,
      confirm_closed: !app.inert && !document.querySelector("#theme-options").inert
        && previewResult.textContent === "Preview confirmed. No files were changed.",
      focus_restored: cancelFocus && document.activeElement === previewButton,
      wheel_blocked: wheelBlocked,
    };
  }
})().catch(reportFailure);
