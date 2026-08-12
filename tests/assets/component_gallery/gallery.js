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

function validAccepted(value) {
  return value !== null &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    Object.keys(value).length === 1 &&
    value.accepted === true;
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
  const CONTROL_CASES = Object.freeze([
    { key: "button", className: "nami-button", tag: "button" },
    { key: "dropdown", className: "nami-select", tag: "select" },
    { key: "tri_state_checkbox", className: "nami-checkbox", tag: "input" },
    { key: "progress_determinate", className: "nami-progress", tag: "progress" },
    { key: "progress_indeterminate", className: "nami-progress", tag: "progress" },
    { key: "text_input", className: "nami-input", tag: "input" },
    { key: "toggle", className: "nami-toggle__control", tag: "input" },
    { key: "chip", className: "nami-chip", tag: "button" },
    { key: "list_row", className: "nami-list-row", tag: "div" },
    { key: "tree_row", className: "nami-tree-row", tag: "div" },
    { key: "card", className: "nami-card", tag: "section" },
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

  const [{ dispatchInteractive }, { renderText }, iconModule] = await Promise.all([
    import("/bridge.js"),
    import("/render.js"),
    import("/icons.js"),
  ]);
  const { createIcon, ICON_NAMES } = iconModule;
  if (typeof createIcon !== "function" || !Array.isArray(ICON_NAMES)) {
    throw new TypeError("installed icon registry has an invalid public shape");
  }
  galleryStage = "page_setup";

  const forced = matchMedia("(forced-colors: active)").matches;
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const dark = matchMedia("(prefers-color-scheme: dark)").matches;
  const mode = forced ? "forced" : reduced ? "reduced" : dark ? "dark" : "light";
  document.documentElement.dataset.theme = dark ? "dark" : "light";
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
      indicator: style.borderColor,
      alias_foreground: aliases.foreground,
      alias_background: aliases.background,
      alias_indicator: aliases.indicator,
      aliases_consumed: style.color === aliases.foreground &&
        style.backgroundColor === aliases.background &&
        style.borderColor === aliases.indicator,
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
      root.setAttribute("role", "group");
      const sync = document.createElement("button");
      sync.className = "nami-segmented__item";
      sync.setAttribute("aria-checked", "false");
      renderText(sync, "Sync");
      const integrity = document.createElement("button");
      integrity.className = "nami-segmented__item";
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
    if (element.tagName === "BUTTON") {
      element.setAttribute("aria-pressed", "false");
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
        surrounding: getComputedStyle(controlsSection).backgroundColor,
        opacity: style.opacity,
        transform: style.transform,
        transition_duration: motionStyle.transitionDuration,
        animation_duration: motionStyle.animationDuration,
        animation_name: motionStyle.animationName,
      });
    }
  }

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
  const controlContract = {
    tri_state: {
      aria_checked: mixedCheckbox.getAttribute("aria-checked"),
      indeterminate: mixedCheckbox.indeterminate,
      cue_content: mixedStyle.content,
    },
  };

  galleryStage = "report";
  await dispatchInteractive(
    "test_report",
    Object.freeze({
      phase: "complete",
      mode,
      media: Object.freeze({ dark, forced, reduced }),
      statuses,
      operations,
      controls,
      control_contract: controlContract,
      motion: Object.freeze({
        nonessential_max_ms: nonessentialMax,
        indeterminate_iteration_count: indeterminateIterationCount,
      }),
      icons: iconEvidence,
    }),
    validAccepted,
  );
  renderText(status, `Gallery ${mode} complete`);
})().catch(reportFailure);
