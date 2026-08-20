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

async function waitForThemeSelector(select, theme, disabled) {
  for (let frame = 0; frame < 300; frame += 1) {
    if (select.value === theme && select.disabled === disabled) {
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
  const STATUS_CASES = Object.freeze([
    { key: "complete", text: "Complete", icon: "checkmark-circle", shape: "circle-check", cue: "Completed" },
    { key: "success", text: "Success", icon: "checkmark-circle", shape: "circle-check", cue: "Succeeded" },
    { key: "failure", text: "Failure", icon: "dismiss-circle", shape: "circle-x", cue: "Failed" },
    { key: "error", text: "Error", icon: "dismiss-circle", shape: "circle-x", cue: "Error" },
    { key: "warning", text: "Warning", icon: "warning", shape: "triangle", cue: "Needs attention" },
    { key: "degraded", text: "Degraded", icon: "warning", shape: "triangle", cue: "Partially available" },
    { key: "incomplete", text: "Incomplete", icon: "warning", shape: "triangle", cue: "Not finished" },
    { key: "active", text: "Active", icon: "info", shape: "circle-info", cue: "In progress" },
    { key: "paused", text: "Paused", icon: "warning", shape: "pause", cue: "Paused" },
    { key: "canceled", text: "Canceled", icon: "dismiss-circle", shape: "circle-x", cue: "Canceled" },
    { key: "mismatch", text: "Mismatch", icon: "dismiss-circle", shape: "split", cue: "Does not match" },
    { key: "blocked", text: "Blocked", icon: "warning", shape: "barrier", cue: "Blocked" },
    { key: "deferred", text: "Deferred", icon: "warning", shape: "clock", cue: "Deferred" },
    { key: "neutral", text: "Neutral", icon: "info", shape: "circle-info", cue: "Informational" },
    { key: "noop", text: "No-op", icon: "info", shape: "dash", cue: "No change" },
  ]);
  const OPERATION_CASES = Object.freeze([
    { key: "copy", text: "Copy", icon: "info", shape: "arrow-right", cue: "New file" },
    { key: "update", text: "Update", icon: "info", shape: "refresh", cue: "Replace content" },
    { key: "move", text: "Move", icon: "info", shape: "paired-arrows", cue: "Relocate" },
    { key: "move_update", text: "Move + update", icon: "info", shape: "paired-refresh", cue: "Relocate and replace" },
    { key: "recase", text: "Recase", icon: "info", shape: "letter-case", cue: "Change name case" },
    { key: "mkdir", text: "Create folder", icon: "checkmark-circle", shape: "folder-plus", cue: "New folder" },
    { key: "trash", text: "Move to trash", icon: "warning", shape: "trash", cue: "Recoverable removal" },
    { key: "delete", text: "Delete", icon: "dismiss-circle", shape: "trash-x", cue: "Permanent removal" },
    { key: "noop", text: "No change", icon: "info", shape: "dash", cue: "No operation" },
  ]);
  const PLAN_ROW_CASES = Object.freeze([
    { key: "plain", rowView: Object.freeze({ checked: true, mixed: false, selectionDisabled: false, selectionLabel: "Select readme.txt", depth: 0, folder: false, expanded: false, nameText: "readme.txt", sizeText: "1.2 KB", intentText: "—", intentTone: "", intentKey: "", checksumText: "5a2f8c10", notesText: "Plain projected file row." }) },
    { key: "mkdir", rowView: Object.freeze({ checked: false, mixed: true, selectionDisabled: false, selectionLabel: "Select photos folder", depth: 0, folder: true, expanded: true, nameText: "photos", sizeText: "14.8 MB", intentText: "Create folder", intentTone: "operation", intentKey: "mkdir", checksumText: "—", notesText: "Partially selected folder." }) },
    { key: "copy", parentKey: "mkdir", rowView: Object.freeze({ checked: true, mixed: false, selectionDisabled: false, selectionLabel: "Select photos DSC_1000.jpeg", depth: 1, folder: false, expanded: false, nameText: "DSC_1000.jpeg", sizeText: "8.1 MB", intentText: "Copy", intentTone: "operation", intentKey: "copy", checksumText: "12ab34cd", notesText: "New child file." }) },
    { key: "update", parentKey: "mkdir", rowView: Object.freeze({ checked: false, mixed: false, selectionDisabled: false, selectionLabel: "Select photos DSC_1001.jpeg", depth: 1, folder: false, expanded: false, nameText: "DSC_1001.jpeg", sizeText: "6.7 MB", intentText: "Update", intentTone: "operation", intentKey: "update", checksumText: "90ef12ab", notesText: "Changed child file." }) },
    { key: "move", rowView: Object.freeze({ checked: true, mixed: false, selectionDisabled: false, selectionLabel: "Select report.pdf", depth: 0, folder: false, expanded: false, nameText: "report.pdf", sizeText: "842 KB", intentText: "Move", intentTone: "operation", intentKey: "move", checksumText: "3456cdef", notesText: "Relocate without replacing bytes." }) },
    { key: "move_update", rowView: Object.freeze({ checked: true, mixed: false, selectionDisabled: false, selectionLabel: "Select notes.md", depth: 0, folder: false, expanded: false, nameText: "notes.md", sizeText: "4.6 KB", intentText: "Move + update", intentTone: "operation", intentKey: "move_update", checksumText: "7890abcd", notesText: "Relocate and replace content." }) },
    { key: "recase", rowView: Object.freeze({ checked: true, mixed: false, selectionDisabled: false, selectionLabel: "Select Logo.PNG", depth: 0, folder: false, expanded: false, nameText: "Logo.PNG", sizeText: "32 KB", intentText: "Recase", intentTone: "operation", intentKey: "recase", checksumText: "bcde1234", notesText: "Change only the path casing." }) },
    { key: "trash", rowView: Object.freeze({ checked: false, mixed: false, selectionDisabled: false, selectionLabel: "Select export.zip", depth: 0, folder: false, expanded: false, nameText: "export.zip", sizeText: "2.4 MB", intentText: "Move to trash", intentTone: "operation", intentKey: "trash", checksumText: "def05678", notesText: "Recoverable removal specimen." }) },
    { key: "delete", rowView: Object.freeze({ checked: false, mixed: false, selectionDisabled: false, selectionLabel: "Select obsolete.tmp", depth: 0, folder: false, expanded: false, nameText: "obsolete.tmp", sizeText: "128 B", intentText: "Delete", intentTone: "operation", intentKey: "delete", checksumText: "1357ace0", notesText: "Permanent removal specimen." }) },
    { key: "noop", rowView: Object.freeze({ checked: false, mixed: false, selectionDisabled: false, selectionLabel: "Select unchanged.bin", depth: 0, folder: false, expanded: false, nameText: "unchanged.bin", sizeText: "16 MB", intentText: "No change", intentTone: "operation", intentKey: "noop", checksumText: "2468bdf1", notesText: "No operation is intended." }) },
    { key: "error", rowView: Object.freeze({ checked: false, mixed: false, selectionDisabled: true, selectionLabel: "Selection unavailable for locked.dat", depth: 0, folder: false, expanded: false, nameText: "locked.dat", sizeText: "—", intentText: "Error", intentTone: "status", intentKey: "error", checksumText: "—", notesText: "The projected row reports a read error." }) },
    { key: "unsupported", rowView: Object.freeze({ checked: false, mixed: false, selectionDisabled: true, selectionLabel: "Selection unavailable for device-link", depth: 0, folder: false, expanded: false, nameText: "device-link", sizeText: "—", intentText: "Unsupported", intentTone: "status", intentKey: "blocked", checksumText: "—", notesText: "Unsupported entry type." }) },
  ]);
  const INTEGRITY_ROW_CASES = Object.freeze([
    { key: "folder", rowView: Object.freeze({ checked: false, mixed: true, selectionDisabled: false, selectionLabel: "Select documents folder", depth: 0, folder: true, expanded: true, nameText: "documents", sizeText: "2.5 MB", presenceText: "Mixed", presenceStatus: "warning", integrityText: "Mixed", integrityStatus: "warning", notesText: "Partially selected folder." }) },
    { key: "match", parentKey: "folder", rowView: Object.freeze({ checked: true, mixed: false, selectionDisabled: false, selectionLabel: "Select documents report.pdf", depth: 1, folder: false, expanded: false, nameText: "report.pdf", sizeText: "2.1 MB", presenceText: "Both", presenceStatus: "complete", integrityText: "Match", integrityStatus: "complete", notesText: "Content matches." }) },
    { key: "source_only", parentKey: "folder", rowView: Object.freeze({ checked: false, mixed: false, selectionDisabled: false, selectionLabel: "Select documents draft.docx", depth: 1, folder: false, expanded: false, nameText: "draft.docx", sizeText: "412 KB", presenceText: "Source only", presenceStatus: "warning", integrityText: "Not compared", integrityStatus: "deferred", notesText: "No target file." }) },
    { key: "mismatch", rowView: Object.freeze({ checked: true, mixed: false, selectionDisabled: false, selectionLabel: "Select archive.zip", depth: 0, folder: false, expanded: false, nameText: "archive.zip", sizeText: "18.4 MB", presenceText: "Both", presenceStatus: "complete", integrityText: "Mismatch", integrityStatus: "mismatch", notesText: "Checksums differ." }) },
    { key: "error", rowView: Object.freeze({ checked: false, mixed: false, selectionDisabled: true, selectionLabel: "Selection unavailable for locked.dat", depth: 0, folder: false, expanded: false, nameText: "locked.dat", sizeText: "—", presenceText: "Unknown", presenceStatus: "error", integrityText: "Error", integrityStatus: "error", notesText: "Read failed." }) },
  ]);
  const CONTROL_CASES = Object.freeze([
    { key: "button", className: "nami-button", tag: "button" },
    { key: "button_primary", className: "nami-button nami-button--primary", tag: "button" },
    { key: "dropdown", className: "nami-select", tag: "select" },
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
  }, { renderText }, iconModule, { renderPlanRow }, { renderIntegrityRow }] = await Promise.all([
    import("/bridge.js"),
    import("/render.js"),
    import("/icons.js"),
    import("/plan.js"),
    import("/integrity.js"),
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
  if (!(themeSelector instanceof HTMLSelectElement)) {
    throw new Error("the product theme selector is unavailable");
  }
  await waitForThemeSelector(themeSelector, expectedTheme, false);
  themeSelector.value = alternateTheme;
  themeSelector.dispatchEvent(new Event("change", { bubbles: true }));
  const changeImmediateValue = themeSelector.value;
  const changeImmediateDisabled = themeSelector.disabled;
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

  themeSelector.value = expectedTheme;
  themeSelector.dispatchEvent(new Event("change", { bubbles: true }));
  const restoreImmediateValue = themeSelector.value;
  const restoreImmediateDisabled = themeSelector.disabled;
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
      final_value: themeSelector.value,
      final_disabled: themeSelector.disabled,
    }),
  });
  document.documentElement.dataset.testGalleryMarker = TEST_ONLY_GALLERY_MARKER;

  const app = document.querySelector("#app");
  if (!(app instanceof HTMLElement)) {
    throw new TypeError("installed page app root is unavailable");
  }
  app.replaceChildren();
  const heading = document.createElement("h1");
  renderText(heading, "NamiSync component gallery");
  app.append(heading);
  const status = document.createElement("p");
  status.id = "host-status";
  status.setAttribute("role", "status");
  renderText(status, `Gallery ${mode} measuring`);
  app.append(status);

  function icon(name, size = "md") {
    const value = createIcon(document, name, size);
    if (!(value instanceof HTMLElement)) {
      throw new TypeError("icon registry did not create an element");
    }
    value.setAttribute("aria-hidden", "true");
    return value;
  }

  function resolvedAlias(prefix, key) {
    const probe = document.createElement("span");
    probe.style.color = `var(--${prefix}-${key}-foreground)`;
    probe.style.backgroundColor = `var(--${prefix}-${key}-background)`;
    probe.style.borderColor = `var(--${prefix}-${key}-indicator)`;
    app.append(probe);
    const style = getComputedStyle(probe);
    const value = {
      foreground: style.color,
      background: style.backgroundColor,
      indicator: style.borderColor,
    };
    probe.remove();
    return value;
  }

  function computedRow(element, definition, prefix, shape, text) {
    const style = getComputedStyle(element);
    const aliases = resolvedAlias(prefix, definition.key);
    const fontSize = parseFloat(style.fontSize);
    const fontWeight = parseInt(style.fontWeight, 10) || 400;
    const shapeStyle = getComputedStyle(shape, "::before");
    const shapeBounds = shape.getBoundingClientRect();
    return {
      key: definition.key,
      text: definition.text,
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
      computedRow(row, definition, prefix, shape, text),
    );
  }

  function controlElement(definition, state) {
    let root = document.createElement(definition.tag);
    let element = root;
    element.className = definition.className;
    if (definition.operation !== undefined) {
      element.dataset.operation = definition.operation;
    }
    if (definition.key === "dropdown") {
      const option = document.createElement("option");
      renderText(option, "Folder");
      element.append(option);
    } else if (definition.key === "tri_state_checkbox") {
      element.type = "checkbox";
      element.setAttribute("aria-checked", "false");
    } else if (definition.key === "progress_determinate") {
      root = document.createElement("div");
      root.className = "nami-progress";
      root.dataset.status = "active";
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
      root.dataset.status = "active";
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
      element.checked = false;
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
    if (element.tagName === "BUTTON" && definition.key !== "segmented_control") {
      element.setAttribute("aria-pressed", String(definition.pressed ?? false));
    }
    if (state === "disabled") {
      if ("disabled" in element) {
        element.disabled = true;
      }
      element.setAttribute("aria-disabled", "true");
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
  const statuses = semanticRows(STATUS_CASES, "status", "nami-status-pill");
  const operations = semanticRows(OPERATION_CASES, "operation", "nami-badge");
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
    for (const [index, text] of headers.entries()) {
      const cell = document.createElement("div");
      cell.className = "nami-file-list__header-cell";
      cell.setAttribute("role", "columnheader");
      if (index === 0) {
        cell.setAttribute("aria-label", "Selection");
      }
      renderText(cell, text);
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
    return { list, grid, header, body };
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
    ["", "Filename", "Size", "Presence", "Integrity", "Notes"],
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

  const pseudoTargets = CONTROL_CASES.flatMap((definition) => [
    { selector: `#gallery-control-${definition.key}-hover`, classes: ["hover"] },
    { selector: `#gallery-control-${definition.key}-pressed`, classes: ["hover", "active"] },
    { selector: `#gallery-control-${definition.key}-focused`, classes: ["focus", "focus-visible"] },
  ]);
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

  const planSectionStyle = getComputedStyle(planSection);
  const planSectionContentWidth = planSection.clientWidth
    - parseFloat(planSectionStyle.paddingLeft)
    - parseFloat(planSectionStyle.paddingRight);
  const galleryUsesWorkArea = planSectionStyle.gridArea === "work";
  function toneAndKey(cell) {
    if (cell.dataset.operation !== undefined) {
      return ["operation", cell.dataset.operation];
    }
    if (cell.dataset.status !== undefined) {
      return ["status", cell.dataset.status];
    }
    return ["", ""];
  }

  function collectFileListEvidence(specimen, definitions) {
    const { list, grid, header, body } = specimen;
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
      const notes = row.querySelector('.nami-file-row__notes');
      if (
        definition === undefined
        || !(checkbox instanceof HTMLInputElement)
        || !(name instanceof HTMLElement)
        || !(size instanceof HTMLElement)
        || !(primary instanceof HTMLElement)
        || !(secondary instanceof HTMLElement)
        || !(notes instanceof HTMLElement)
        || cells.length !== 6
        || !cells.every((cell) => cell instanceof HTMLElement)
      ) {
        throw new TypeError("gallery file row structure is unavailable");
      }
      const [primaryTone, primaryKey] = toneAndKey(primary);
      const [secondaryTone, secondaryKey] = toneAndKey(secondary);
      const primaryColor = getComputedStyle(primary).color;
      const secondaryColor = getComputedStyle(secondary).color;
      const disclosure = row.querySelector(".nami-file-row__disclosure");
      const checkboxBounds = checkbox.getBoundingClientRect();
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
        secondary: secondary.textContent,
        secondary_tone: secondaryTone,
        secondary_key: secondaryKey,
        notes: notes.textContent,
        background: getComputedStyle(row).backgroundColor,
        primary_color: primaryColor,
        primary_alias_color: primaryTone === ""
          ? primaryColor
          : resolvedAlias(primaryTone, primaryKey).foreground,
        secondary_color: secondaryColor,
        secondary_alias_color: secondaryTone === ""
          ? secondaryColor
          : resolvedAlias(secondaryTone, secondaryKey).foreground,
        cell_backgrounds: cells.map(
          (cell) => getComputedStyle(cell).backgroundColor,
        ),
        column_lefts: cells.map(
          (cell) => Number(cell.getBoundingClientRect().left.toFixed(3)),
        ),
        name_padding_left: Number(
          parseFloat(getComputedStyle(name).paddingLeft).toFixed(3),
        ),
        row_height: row.getBoundingClientRect().height,
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
  const dialogExit = await dialogExitEvidence();
  const controlContract = {
    tri_state: {
      aria_checked: mixedCheckbox.getAttribute("aria-checked"),
      indeterminate: mixedCheckbox.indeterminate,
      cue_content: mixedStyle.content,
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
    file_list: planEvidence,
    integrity_list: integrityEvidence,
  };

  galleryStage = "report";
  const reportParts = [
    { name: "statuses", value: statuses },
    { name: "operations", value: operations },
  ];
  for (let offset = 0; offset < controls.length; offset += CONTROL_REPORT_CHUNK_ROWS) {
    reportParts.push({
      name: "controls",
      value: controls.slice(offset, offset + CONTROL_REPORT_CHUNK_ROWS),
    });
  }
  reportParts.push(
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
      media: Object.freeze({ dark, forced, reduced }),
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
