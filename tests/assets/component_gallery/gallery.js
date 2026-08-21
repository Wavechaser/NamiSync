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
const PSEUDO_STATE_SETTLE_MS = 350;
const CONTROL_REPORT_CHUNK_ROWS = 10;

function validAccepted(value) {
  return value !== null &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    Object.keys(value).length === 1 &&
    value.accepted === true;
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

async function reportFailure(error) {
  const candidate = error !== null && typeof error === "object" ? error.name : "";
  const type = FAILURE_TYPES.has(candidate) ? candidate : "Error";
  const failure = Object.freeze({ stage: galleryStage, type });
  try {
    const { dispatchInteractive } = await import("/bridge.js");
    await dispatchInteractive(
      "test_report",
      Object.freeze({ phase: "failure", failure }),
      validAccepted,
    );
  } catch {
    // The native scenario deadline remains authoritative when transport is gone.
  }
  const target = document.querySelector("#host-status");
  if (target instanceof HTMLElement) {
    target.textContent = `Gallery failed: ${type}`;
  }
}

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
    { key: "failed", text: "Failed", hue: "red", form: "fill", icon: "dismiss-circle", shape: "circle-x", cue: "The run failed" },
    { key: "errored", text: "Errored", hue: "red", form: "fill", icon: "dismiss-circle", shape: "circle-x", cue: "The run encountered an error" },
  ]);
  const INTENT_CASES = Object.freeze([
    { key: "copy", text: "Copy", hue: "blue", form: "text", icon: "info", shape: "arrow-right", cue: "New file" },
    { key: "mkdir", text: "Create folder", hue: "blue", form: "text", icon: "checkmark-circle", shape: "folder-plus", cue: "New folder" },
    { key: "move", text: "Move", hue: "purple", form: "text", icon: "info", shape: "paired-arrows", cue: "Relocate" },
    { key: "recase", text: "Recase", hue: "purple", form: "text", icon: "info", shape: "letter-case", cue: "Change name case" },
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
    { key: "copying", rowView: Object.freeze({ checked: true, mixed: false, selectionDisabled: false, selectionLabel: "Select active-copy.bin", depth: 0, folder: false, expanded: false, nameText: "active-copy.bin", sizeText: "24 MB", intentText: "Copying", intentKey: "", lifecycleKey: "executing", checksumText: "—", notesText: "Projected execution is in progress." }) },
    { key: "completed", rowView: Object.freeze({ checked: true, mixed: false, selectionDisabled: false, selectionLabel: "Select completed-copy.bin", depth: 0, folder: false, expanded: false, nameText: "completed-copy.bin", sizeText: "12 MB", intentText: "Completed", intentKey: "", lifecycleKey: "completed", checksumText: "5a2f8c10", notesText: "Projected execution completed." }) },
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
    { key: "verifying", rowView: Object.freeze({ checked: true, mixed: false, selectionDisabled: false, selectionLabel: "Select verifying.iso", depth: 0, folder: false, expanded: false, nameText: "verifying.iso", sizeText: "1.4 GB", presenceText: "Verifying", presenceStatus: "", lifecycleKey: "verifying", checksumText: "—", notesText: "Projected integrity verification is in progress." }) },
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
    { key: "dropdown", className: "nami-combobox__trigger", tag: "button" },
    { key: "tri_state_checkbox", className: "nami-checkbox", tag: "input" },
    { key: "progress_determinate", className: "nami-progress", tag: "progress" },
    { key: "progress_indeterminate", className: "nami-progress", tag: "progress" },
    { key: "text_input", className: "nami-input", tag: "input" },
    { key: "toggle", className: "nami-toggle__control", tag: "input" },
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
  const ICON_CONTRACT = Object.freeze([
    "checkmark-circle",
    "dismiss-circle",
    "warning",
    "info",
  ]);

  const [{
    dispatchInteractive,
    readCosmeticSection,
    replaceCosmeticSection,
  }, { renderText }, iconModule, { renderPlanRow }, { renderIntegrityRow }, { createTaskRail }] = await Promise.all([
    import("/bridge.js"),
    import("/render.js"),
    import("/icons.js"),
    import("/plan.js"),
    import("/integrity.js"),
    import("/rail.js"),
  ]);
  const { createIcon, ICON_NAMES } = iconModule;
  if (
    typeof createIcon !== "function"
    || !Array.isArray(ICON_NAMES)
    || typeof renderPlanRow !== "function"
    || typeof renderIntegrityRow !== "function"
  ) {
    throw new TypeError("installed icon registry has an invalid public shape");
  }
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

  const galleryRail = createTaskRail();
  const taskSlot = galleryRail.querySelector(".nami-task-rail__empty-slot");
  if (!(taskSlot instanceof HTMLElement)) {
    throw new TypeError("gallery task rail slot is unavailable");
  }
  taskSlot.classList.remove("nami-card", "nami-task-rail__empty-slot");
  taskSlot.classList.add("nami-task-rail__specimens");
  taskSlot.replaceChildren();
  for (const definition of [
    { label: "Current sync", state: "selected_current", lifecycle: "executing", form: "text", status: "Executing" },
    { label: "Paused verification", state: "rest", lifecycle: "paused", form: "text", status: "Paused" },
    { label: "Canceled sync", state: "rest", lifecycle: "canceled", form: "fill", status: "Canceled" },
  ]) {
    const task = document.createElement("button");
    task.className = "nami-task-card";
    task.type = "button";
    task.dataset.galleryTask = definition.lifecycle;
    if (definition.state === "selected_current") {
      task.setAttribute("aria-selected", "true");
      task.setAttribute("aria-current", "true");
    }
    const label = document.createElement("span");
    renderText(label, definition.label);
    const state = document.createElement("span");
    state.className = "nami-status-pill";
    state.dataset.lifecycle = definition.lifecycle;
    state.dataset.form = definition.form;
    renderText(state, definition.status);
    task.append(label, state);
    taskSlot.append(task);
  }
  app.append(galleryRail);

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
    if (definition.key === "dropdown") {
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
    } else if (definition.key === "toggle") {
      root = document.createElement("label");
      root.className = "nami-toggle";
      element = document.createElement("input");
      element.className = "nami-toggle__control";
      element.type = "checkbox";
      element.setAttribute("role", "switch");
      element.checked = true;
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
  const planSection = document.createElement("section");
  planSection.className = "nami-card";
  planSection.dataset.gallerySection = "plan_rows";
  planSection.style.gridArea = "work";
  function createFileList(title, label, headers, definitions, renderer, caseName) {
    const heading = document.createElement("h2");
    renderText(heading, title);
    const list = document.createElement("div");
    list.className = "nami-file-list";
    list.setAttribute("role", "table");
    list.setAttribute("aria-label", label);
    const grid = document.createElement("div");
    grid.className = "nami-file-list__grid";
    const header = document.createElement("div");
    header.className = "nami-file-list__header";
    header.setAttribute("role", "row");
    const columnNames = ["selection", "name", "size", "primary", "secondary", "notes"];
    const columnMinimums = [32, 128, 64, 96, 80, 160];
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
      const resizer = document.createElement("div");
      resizer.className = "nami-file-list__column-resizer";
      resizer.dataset.column = columnNames[index];
      resizer.dataset.minimum = String(columnMinimums[index]);
      resizer.setAttribute("role", "separator");
      resizer.setAttribute("aria-orientation", "vertical");
      resizer.setAttribute(
        "aria-label",
        `Resize ${text || "selection"} column`,
      );
      resizer.tabIndex = 0;
      cell.append(resizer);
      header.append(cell);
    }
    const body = document.createElement("div");
    body.className = "nami-file-list__body";
    body.setAttribute("role", "rowgroup");
    for (const definition of definitions) {
      const row = document.createElement("div");
      renderer(row, definition.rowView);
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
    for (const resizer of header.querySelectorAll(
      ".nami-file-list__column-resizer",
    )) {
      const property = `--nami-file-column-${resizer.dataset.column}`;
      const minimum = Number(resizer.dataset.minimum);
      const cell = resizer.parentElement;
      if (!(cell instanceof HTMLElement) || !Number.isFinite(minimum)) {
        throw new TypeError("gallery column resizer is invalid");
      }
      const setWidth = (width) => {
        const next = Math.max(minimum, Math.min(640, width));
        grid.style.setProperty(property, `${next}px`);
        resizer.setAttribute("aria-valuemin", String(minimum));
        resizer.setAttribute("aria-valuemax", "640");
        resizer.setAttribute("aria-valuenow", String(Math.round(next)));
      };
      resizer.setAttribute("aria-valuemin", String(minimum));
      resizer.setAttribute("aria-valuemax", "640");
      resizer.setAttribute(
        "aria-valuenow",
        String(Math.round(cell.getBoundingClientRect().width)),
      );
      resizer.addEventListener("pointerdown", (event) => {
        event.preventDefault();
        const startX = event.clientX;
        const startWidth = cell.getBoundingClientRect().width;
        const move = (moveEvent) => setWidth(
          startWidth + moveEvent.clientX - startX,
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
        const direction = event.key === "ArrowRight" ? 1 : -1;
        setWidth(cell.getBoundingClientRect().width + direction * 8);
      });
    }
    return { list, grid, header, body, masterCheckbox };
  }

  const planSpecimen = createFileList(
    "Projected sync plan rows",
    "Projected sync plan specimen",
    ["", "Filename", "Size", "Operation / status", "Checksum", "Notes"],
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
        fill_background: motionStyle.backgroundColor,
        border: style.borderColor,
        border_width: style.borderWidth,
        border_style: style.borderStyle,
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
    const { list, grid, header, body, masterCheckbox } = specimen;
    const fillsWorkArea = Math.abs(
      list.getBoundingClientRect().width - planSectionContentWidth,
    ) < 0.5;
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
    const nameResizer = header.querySelector(
      '.nami-file-list__column-resizer[data-column="name"]',
    );
    const firstNameCell = body.querySelector(".nami-file-row__name");
    if (
      !(nameResizer instanceof HTMLElement)
      || !(firstNameCell instanceof HTMLElement)
    ) {
      throw new TypeError("gallery column resize specimen is unavailable");
    }
    const widthBeforeResize = firstNameCell.getBoundingClientRect().width;
    nameResizer.dispatchEvent(new PointerEvent("pointerdown", {
      bubbles: true,
      clientX: 200,
    }));
    window.dispatchEvent(new PointerEvent("pointermove", { clientX: 240 }));
    window.dispatchEvent(new PointerEvent("pointerup", { clientX: 240 }));
    const resizeDelta = firstNameCell.getBoundingClientRect().width
      - widthBeforeResize;
    const columnResizeChangesWidth = resizeDelta > 39 && resizeDelta < 41;
    grid.style.removeProperty("--nami-file-column-name");

    list.style.setProperty("inline-size", "36rem");
    const renderedRows = [...body.children];
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
      const notes = row.querySelector('.nami-file-row__notes');
      if (
        definition === undefined
        || !(checkbox instanceof HTMLInputElement)
        || !(name instanceof HTMLElement)
        || !(size instanceof HTMLElement)
        || !(primary instanceof HTMLElement)
        || !(secondary instanceof HTMLElement)
        || !(primaryLabel instanceof HTMLElement)
        || !(notes instanceof HTMLElement)
        || cells.length !== 6
        || !cells.every((cell) => cell instanceof HTMLElement)
      ) {
        throw new TypeError("gallery file row structure is unavailable");
      }
      const [primaryTone, primaryKey] = toneAndKey(primary);
      const [secondaryTone, secondaryKey] = toneAndKey(secondary);
      const primaryStyle = getComputedStyle(primaryLabel);
      const primaryColor = primaryStyle.color;
      const primaryBackground = primaryStyle.backgroundColor;
      const primaryBounds = primaryLabel.getBoundingClientRect();
      const primaryAliases = resolvedStateAliases(primary);
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
        primary: primary.textContent,
        primary_tone: primaryTone,
        primary_key: primaryKey,
        primary_form: primaryTone === ""
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
    if (
      !(lastRow instanceof HTMLElement)
      || headerCells.length !== 6
      || !headerCells.every((cell) => cell instanceof HTMLElement)
    ) {
      throw new TypeError("gallery file list structure is unavailable");
    }
    const rowsHeight = renderedRows.reduce(
      (total, row) => total + row.getBoundingClientRect().height,
      0,
    );
    const headerStyle = getComputedStyle(header);
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
      resize_handle_count: header.querySelectorAll(
        ".nami-file-list__column-resizer",
      ).length,
      column_resize_changes_width: columnResizeChangesWidth,
      column_resize_delta: Number(resizeDelta.toFixed(3)),
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
      horizontal_overflow: list.scrollWidth > list.clientWidth,
      overflow_x: getComputedStyle(list).overflowX,
      client_width: list.clientWidth,
      scroll_width: list.scrollWidth,
      rows,
    };
    list.style.removeProperty("inline-size");
    return evidence;
  }

  const planEvidence = collectFileListEvidence(planSpecimen, PLAN_ROW_CASES);
  const integrityEvidence = collectFileListEvidence(
    integritySpecimen,
    INTEGRITY_ROW_CASES,
  );

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
  const maskImages = Object.fromEntries(ICON_CONTRACT.map((name) => {
    const glyph = galleryIcons.find((candidate) =>
      candidate.classList.contains(`nami-icon--${name}`),
    );
    return [name, glyph === undefined ? "" : getComputedStyle(glyph).maskImage];
  }));
  const iconEvidence = {
    registry_frozen: Object.isFrozen(ICON_NAMES),
    registry_names: [...ICON_NAMES],
    all_registry_created: ICON_CONTRACT.every((name) =>
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
    system_colors: systemColors,
  };
  const mixedStyle = getComputedStyle(mixedCheckbox, "::after");
  const mixedCheckboxStyle = getComputedStyle(mixedCheckbox);
  const uncheckedCheckboxStyle = getComputedStyle(uncheckedCheckbox);
  const dialogExit = await dialogExitEvidence();
  themeTrigger.blur();
  themeTrigger.click();
  await new Promise((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const themePopup = document.querySelector("#theme-options");
  const selectedThemeOption = themePopup?.querySelector(
    '.nami-combobox__option[aria-selected="true"]',
  );
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
  const taskCards = [...galleryRail.querySelectorAll(".nami-task-card")];
  const selectedTaskCard = galleryRail.querySelector(
    '.nami-task-card[aria-selected="true"]',
  );
  const currentTaskCard = galleryRail.querySelector(
    '.nami-task-card[aria-current="true"]',
  );
  if (
    !(selectedTaskCard instanceof HTMLElement)
    || !(currentTaskCard instanceof HTMLElement)
  ) {
    throw new TypeError("gallery selected task specimens are unavailable");
  }
  const taskRailBounds = galleryRail.getBoundingClientRect();
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
  const controlContract = {
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
    },
    dialog_exit: dialogExit,
    segmented: (() => {
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
      selected_count: galleryRail.querySelectorAll(
        '.nami-task-card[aria-selected="true"]',
      ).length,
      current_count: galleryRail.querySelectorAll(
        '.nami-task-card[aria-current="true"]',
      ).length,
      selected_current_same_card: selectedTaskCard === currentTaskCard,
      transparent_boundaries: taskCards.every((task) => {
        const style = getComputedStyle(task);
        return style.borderStyle === "none" || parseFloat(style.borderWidth) === 0;
      }),
      selected_marker_width: parseFloat(
        getComputedStyle(selectedTaskCard, "::before").width,
      ),
      current_marker_width: parseFloat(
        getComputedStyle(currentTaskCard, "::before").width,
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
    { name: "control_contract", value: controlContract },
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
      }),
      cosmetic: cosmeticEvidence,
      part_count: reportParts.length,
    }),
    validAccepted,
  );
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
})().catch(reportFailure);
