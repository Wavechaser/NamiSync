import { createIcon } from "./icons.js";
import { renderFilesystemText, renderText } from "./render.js";

const MAX_BATCH_PAIRS = 48;
const CALLBACKS = ["onEdit", "onValidate", "onPick", "onRecent", "onRecentPair", "onRefreshRecents", "onMode", "onOption", "onAddFilter", "onRemoveFilter", "onMount", "onPlanAgainMount", "onStartPlan", "onStartInventory", "onAddPair", "onStartBatch", "onPlanAgain"];

function createButton(text, classes = "nami-button") {
  const button = document.createElement("button");
  button.type = "button";
  button.classList.add(...classes.split(" "));
  renderText(button, text);
  return button;
}

function createToggle(text, key, handler) {
  const label = document.createElement("label");
  const input = document.createElement("input");
  const caption = document.createElement("span");
  label.classList.add("nami-toggle", "nami-setup__option");
  input.classList.add("nami-toggle__control");
  input.type = "checkbox";
  input.setAttribute("role", "switch");
  input.dataset.option = key;
  renderText(caption, text);
  input.addEventListener("change", () => handler(key, input.checked));
  label.append(input, caption);
  return { label, input };
}

function createLocationRow(purpose, handlers) {
  const field = document.createElement("div");
  const label = document.createElement("label");
  const line = document.createElement("div");
  const pathControl = document.createElement("div");
  const input = document.createElement("input");
  const clear = createButton("", "nami-button nami-button--icon nami-setup__clear");
  const recentTrigger = createButton("", "nami-button nami-setup__recent-trigger");
  const caret = document.createElement("span");
  const popup = document.createElement("div");
  const picker = createButton("", "nami-button nami-button--icon nami-setup__picker");
  const status = document.createElement("p");
  const mounts = document.createElement("div");
  let locations = [];
  let active = -1;
  let recentSignature = "";

  field.classList.add("nami-field", "nami-setup__location");
  field.dataset.purpose = purpose;
  line.classList.add("nami-setup__location-line");
  pathControl.classList.add("nami-setup__path-control");
  input.classList.add("nami-input", "nami-setup__path");
  input.type = "text";
  input.autocomplete = "off";
  input.spellcheck = false;
  input.id = `setup-${purpose}-path`;
  input.setAttribute("aria-describedby", `setup-${purpose}-status`);
  label.htmlFor = input.id;
  renderText(label, purpose === "source" ? "Source" : "Target");
  clear.title = `Clear ${purpose} folder`;
  clear.ariaLabel = `Clear ${purpose} folder`;
  clear.append(createIcon(document, "dismiss", "sm"));
  recentTrigger.id = `setup-${purpose}-recent-trigger`;
  recentTrigger.ariaHasPopup = "listbox";
  recentTrigger.ariaExpanded = "false";
  recentTrigger.setAttribute("aria-controls", `setup-${purpose}-recent-popup`);
  recentTrigger.title = `Choose a recent ${purpose} folder`;
  recentTrigger.ariaLabel = `Choose a recent ${purpose} folder`;
  caret.classList.add("nami-setup__caret");
  caret.ariaHidden = "true";
  recentTrigger.append(caret);
  popup.id = `setup-${purpose}-recent-popup`;
  popup.classList.add("nami-combobox__popup", "nami-setup__recent-popup");
  popup.setAttribute("role", "listbox");
  popup.ariaLabel = `Recent ${purpose} folders`;
  popup.hidden = true;
  picker.title = `Browse for ${purpose} folder`;
  picker.ariaLabel = `Browse for ${purpose} folder`;
  picker.append(createIcon(document, "folder-open", "sm"));
  status.id = `setup-${purpose}-status`;
  status.classList.add("nami-field__hint", "nami-setup__location-status");
  status.setAttribute("role", "status");
  mounts.classList.add("nami-setup__mounts");
  pathControl.append(input, clear, recentTrigger, popup);
  line.append(label, pathControl, picker);
  field.append(line, status, mounts);

  function setOpen(open, focus = false, restoreFocus = false) {
    const focusWasInside = !popup.hidden && popup.contains(document.activeElement);
    const allowed = open && !recentTrigger.disabled && locations.length > 0;
    popup.hidden = !allowed;
    recentTrigger.ariaExpanded = String(allowed);
    if (!allowed) {
      active = -1;
      if (focusWasInside && restoreFocus) {
        if (!recentTrigger.disabled) recentTrigger.focus();
        else if (!input.disabled) input.focus();
      }
      return focusWasInside;
    }
    active = Math.max(0, Math.min(active, locations.length - 1));
    const options = [...popup.querySelectorAll("[role=option]")];
    options.forEach((option, index) => option.toggleAttribute("data-active", index === active));
    if (focus) options[active]?.focus();
    return false;
  }
  function choose(index) {
    if (recentTrigger.disabled || locations[index] === undefined) return;
    const location = locations[index];
    setOpen(false);
    handlers.onRecent(purpose, location);
    recentTrigger.focus();
  }
  function move(delta) {
    active = (active + delta + locations.length) % locations.length;
    setOpen(true, true);
  }
  recentTrigger.addEventListener("click", () => setOpen(popup.hidden));
  recentTrigger.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      active = event.key === "ArrowDown" ? 0 : locations.length - 1;
      setOpen(true, true);
    } else if (event.key === "Escape" && !popup.hidden) { event.preventDefault(); setOpen(false); }
    else if (event.key === "Tab") setOpen(false);
  });
  popup.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") { event.preventDefault(); move(event.key === "ArrowDown" ? 1 : -1); }
    else if (event.key === "Home" || event.key === "End") { event.preventDefault(); active = event.key === "Home" ? 0 : locations.length - 1; setOpen(true, true); }
    else if (event.key === "Enter" || event.key === " ") { event.preventDefault(); choose(active); }
    else if (event.key === "Escape") { event.preventDefault(); setOpen(false); recentTrigger.focus(); }
    else if (event.key === "Tab") setOpen(false);
  });
  document.addEventListener?.("pointerdown", (event) => { if (!popup.hidden && !field.contains(event.target)) setOpen(false); });
  document.addEventListener?.("focusin", (event) => { if (!popup.hidden && !field.contains(event.target)) setOpen(false); });
  const validate = () => handlers.onValidate(purpose);
  input.addEventListener("input", () => {
    clear.hidden = input.value.length === 0;
    handlers.onEdit(purpose, input.value);
  });
  input.addEventListener("blur", (event) => {
    if (event.relatedTarget !== clear) validate();
  });
  input.addEventListener("keydown", (event) => { if (event.key === "Enter") { event.preventDefault(); validate(); } });
  input.addEventListener("paste", () => queueMicrotask(validate));
  picker.addEventListener("click", () => handlers.onPick(purpose));
  clear.addEventListener("pointerdown", (event) => event.preventDefault());
  clear.addEventListener("click", () => {
    input.value = "";
    clear.hidden = true;
    setOpen(false);
    handlers.onEdit(purpose, "");
    input.focus();
  });

  function renderRecents(values, editable) {
    locations = values;
    recentTrigger.disabled = !editable || values.length === 0;
    const signature = values.map((location) => `${location.location_id}\u0000${location.display}`).join("\u0001");
    if (signature !== recentSignature) {
      setOpen(false, false, true);
      recentSignature = signature;
      popup.replaceChildren();
      values.forEach((location, index) => {
        const option = createButton("", "nami-combobox__option nami-setup__recent");
        option.setAttribute("role", "option");
        option.dataset.locationId = location.location_id;
        option.tabIndex = -1;
        renderFilesystemText(option, location.display);
        option.addEventListener("click", () => choose(index));
        popup.append(option);
      });
    }
    if (recentTrigger.disabled) setOpen(false);
  }
  return { field, label, input, clear, picker, status, mounts, renderRecents, setOpen };
}

function locationStatus(location) {
  if (location == null) return "";
  if (location.state === "resolved") return "";
  return location.detail ?? "That folder is not available.";
}

function availabilityLabel(state) {
  return state === "online" ? "Online" : state === "offline" ? "Offline"
    : state === "unavailable" ? "Unavailable" : state === "checking" ? "Checking…" : "Could not check";
}

export function createSetupPanel(callbacks) {
  const handlers = {};
  CALLBACKS.forEach((name) => {
    if (typeof callbacks?.[name] !== "function") throw new TypeError(`${name} must be callable`);
    handlers[name] = callbacks[name];
  });
  const root = document.createElement("div");
  const setupCard = document.createElement("section");
  const recentCard = document.createElement("section");
  const heading = document.createElement("h2");
  const guidance = document.createElement("p");
  const actionStatus = document.createElement("p");
  const modeGroup = document.createElement("div");
  const modeLabel = document.createElement("p");
  const mode = document.createElement("div");
  const modeButtons = new Map();
  const source = createLocationRow("source", handlers);
  const target = createLocationRow("target", handlers);
  const options = document.createElement("div");
  const primaryOptions = document.createElement("div");
  const moreSummary = createButton("More options", "nami-button nami-button--subtle nami-setup__more-summary");
  const moreCaret = document.createElement("span");
  const advancedOptions = document.createElement("div");
  const optionsList = document.createElement("div");
  const filters = document.createElement("div");
  const filterLabel = document.createElement("label");
  const filterControls = document.createElement("div");
  const filterInput = document.createElement("input");
  const addFilter = createButton("Add filter");
  const filterList = document.createElement("ul");
  const actions = document.createElement("div");
  const startPlan = createButton("Create plan", "nami-button nami-button--primary nami-setup__primary-action");
  const startInventory = createButton("Create inventory", "nami-button nami-button--primary nami-setup__primary-action");
  const addPair = createButton("Add pair", "nami-button nami-setup__pair-action nami-setup__add-pair");
  const startBatch = createButton("Create pair batch", "nami-button nami-button--primary nami-setup__pair-action");
  const planAgain = createButton("Plan again", "nami-button nami-setup__primary-action");
  const planAgainChoices = document.createElement("div");
  const batch = document.createElement("ol");
  const recentHeader = document.createElement("div");
  const recentHeading = document.createElement("h2");
  const refreshRecents = createButton("", "nami-button nami-button--subtle nami-button--icon nami-setup__refresh-recents");
  const recentEmpty = document.createElement("p");
  const recentTable = document.createElement("table");
  const recentBody = document.createElement("tbody");
  const recentRows = new Map();
  let locationContext = null;
  let renderedModel = null;
  let moreExpanded = false;

  root.classList.add("nami-work-panel__setup", "nami-setup");
  setupCard.classList.add("nami-card", "nami-setup__card");
  recentCard.classList.add("nami-card", "nami-setup__card", "nami-setup__recent-pairs");
  renderText(heading, "Setup");
  heading.tabIndex = -1;
  renderText(guidance, "Choose folders to create a reviewed plan or inventory task.");
  actionStatus.classList.add("nami-field__hint", "nami-setup__action-status");
  actionStatus.setAttribute("role", "status");
  modeGroup.classList.add("nami-setup__mode-group");
  modeLabel.id = "setup-task-type-label";
  renderText(modeLabel, "Task type");
  mode.classList.add("nami-segmented", "nami-setup__mode");
  mode.setAttribute("role", "radiogroup");
  mode.setAttribute("aria-labelledby", modeLabel.id);
  [["sync-plan", "Sync plan"], ["inventory", "Inventory"]].forEach(([value, text]) => {
    const button = createButton(text, "nami-segmented__item");
    button.setAttribute("role", "radio");
    button.dataset.value = value;
    button.addEventListener("click", () => handlers.onMode(value));
    button.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) return;
      event.preventDefault();
      const next = value === "sync-plan" ? "inventory" : "sync-plan";
      if (!modeButtons.get(next).disabled) {
        handlers.onMode(next);
        modeButtons.get(next).focus();
      }
    });
    modeButtons.set(value, button);
    mode.append(button);
  });
  modeGroup.append(modeLabel, mode);
  options.classList.add("nami-setup__options");
  primaryOptions.classList.add("nami-setup__primary-options");
  const optionInputs = new Map();
  const verify = createToggle("Verify execution", "verify_after_execute", handlers.onOption);
  const additive = createToggle("Additive sync", "deletion_policy", (_key, checked) => {
    handlers.onOption("deletion_policy", checked ? "additive" : "trash");
  });
  verify.label.classList.add("nami-setup__verify-row");
  additive.label.classList.add("nami-setup__additive-row");
  optionInputs.set("verify_after_execute", verify.input);
  primaryOptions.append(verify.label, additive.label, moreSummary);
  moreSummary.ariaExpanded = "false";
  moreSummary.setAttribute("aria-controls", "setup-advanced-options");
  moreCaret.classList.add("nami-setup__more-caret");
  moreCaret.ariaHidden = "true";
  moreSummary.append(moreCaret);
  optionsList.classList.add("nami-setup__options-list");
  for (const [key, text] of [["trash_on_update", "Move replaced target files to trash"], ["preserve_created", "Preserve creation time"], ["preserve_acl", "Preserve access control lists"], ["propagate_source_casing", "Use source casing"]]) {
    const toggle = createToggle(text, key, handlers.onOption);
    optionInputs.set(key, toggle.input);
    optionsList.append(toggle.label);
  }
  const ads = createToggle("Preserve alternate data streams", "preserve_ads", handlers.onOption);
  ads.input.disabled = true;
  ads.label.title = "Alternate data stream preservation is unavailable.";
  optionsList.append(ads.label);
  filterLabel.htmlFor = "setup-filter";
  renderText(filterLabel, "Exclude filters");
  filterInput.id = "setup-filter";
  filterInput.classList.add("nami-input");
  filterInput.type = "text";
  filterInput.autocomplete = "off";
  filterInput.spellcheck = false;
  const submitFilter = () => {
    if (filterInput.value.length === 0) return;
    handlers.onAddFilter(filterInput.value);
    filterInput.value = "";
  };
  addFilter.addEventListener("click", submitFilter);
  filterInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      submitFilter();
    }
  });
  filters.classList.add("nami-setup__filters");
  filterControls.classList.add("nami-setup__filter-controls");
  filterList.classList.add("nami-setup__filter-list");
  filterControls.append(filterInput, addFilter);
  filters.append(filterLabel, filterControls, filterList);
  advancedOptions.classList.add("nami-setup__advanced-options");
  advancedOptions.id = "setup-advanced-options";
  advancedOptions.hidden = true;
  advancedOptions.append(optionsList, filters);
  options.append(primaryOptions, advancedOptions);
  moreSummary.addEventListener("click", () => {
    moreExpanded = !moreExpanded;
    moreSummary.ariaExpanded = String(moreExpanded);
    advancedOptions.hidden = !moreExpanded;
  });
  actions.classList.add("nami-setup__actions");
  actions.append(startPlan, startInventory, addPair, startBatch, planAgain);
  planAgainChoices.classList.add("nami-setup__plan-again-mounts");
  batch.classList.add("nami-setup__batch");
  batch.ariaLabel = "Pair creation results";
  recentHeader.classList.add("nami-setup__recent-header");
  renderText(recentHeading, "Recent pairs");
  refreshRecents.title = "Refresh recent pairs";
  refreshRecents.ariaLabel = "Refresh recent pairs";
  refreshRecents.append(createIcon(document, "arrow-clockwise", "sm"));
  recentHeader.append(recentHeading, refreshRecents);
  renderText(recentEmpty, "No recent pairs yet.");
  recentEmpty.classList.add("nami-shell__guidance", "nami-setup__recent-empty");
  recentTable.classList.add("nami-table", "nami-setup__recent-pair-table");
  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  ["Folders", "Availability"].forEach((text) => {
    const th = document.createElement("th");
    th.scope = "col";
    renderText(th, text);
    headerRow.append(th);
  });
  thead.append(headerRow);
  recentTable.append(thead, recentBody);
  setupCard.append(heading, guidance, actionStatus, modeGroup, source.field, target.field, options, actions, planAgainChoices, batch);
  recentCard.append(recentHeader, recentEmpty, recentTable);
  root.append(setupCard, recentCard);
  startPlan.addEventListener("click", () => handlers.onStartPlan());
  startInventory.addEventListener("click", () => handlers.onStartInventory());
  addPair.addEventListener("click", () => handlers.onAddPair());
  startBatch.addEventListener("click", () => handlers.onStartBatch());
  planAgain.addEventListener("click", () => handlers.onPlanAgain());
  refreshRecents.addEventListener("click", () => handlers.onRefreshRecents());

  function renderLocation(row, value, recents, editable, text) {
    if (document.activeElement !== row.input && row.input.value !== value.text) row.input.value = value.text;
    row.input.dataset.state = value.location?.state ?? "unresolved";
    const message = locationStatus(value.location);
    renderText(row.status, message);
    row.status.hidden = message.length === 0;
    row.renderRecents(recents, editable);
    renderText(row.label, text);
    row.mounts.replaceChildren();
    const candidates = value.location?.state === "ambiguous" && (typeof value.continuationId === "string" || value.candidate !== null) ? value.location.candidates : [];
    candidates.forEach((candidate, index) => {
      const button = createButton("", "nami-button nami-setup__mount");
      button.dataset.mountIndex = String(index);
      button.dataset.selected = String(value.mountIndex === index);
      button.ariaPressed = String(value.mountIndex === index);
      renderFilesystemText(button, candidate);
      button.disabled = !editable;
      button.addEventListener("click", () => handlers.onMount(row.field.dataset.purpose, index));
      row.mounts.append(button);
    });
    row.input.disabled = !editable;
    row.clear.hidden = row.input.value.length === 0;
    row.clear.disabled = !editable;
    row.picker.disabled = !editable;
    if (!editable) row.setOpen(false);
  }
  function renderRecentPairs(values, availability, editable) {
    const retainedIds = new Set(values.map((pair) => pair.mapping_id));
    for (const [mappingId, retained] of recentRows) {
      if (!retainedIds.has(mappingId)) {
        retained.row.remove();
        recentRows.delete(mappingId);
      }
    }
    values.forEach((pair, index) => {
      const states = availability?.[pair.mapping_id] ?? { source: "unknown", target: "unknown" };
      const online = states.source === "online" && states.target === "online";
      let retained = recentRows.get(pair.mapping_id);
      if (retained === undefined) {
        const row = document.createElement("tr");
        const paths = document.createElement("td");
        const select = createButton("", "nami-button nami-setup__pair-select");
        const sourcePath = document.createElement("span");
        const targetPath = document.createElement("span");
        const statuses = {};
        row.classList.add("nami-setup__recent-pair");
        row.dataset.mappingId = pair.mapping_id;
        paths.classList.add("nami-setup__pair-folders");
        select.dataset.mappingId = pair.mapping_id;
        sourcePath.classList.add("nami-setup__pair-path");
        targetPath.classList.add("nami-setup__pair-path");
        select.append(sourcePath, targetPath);
        paths.append(select);
        const statusCell = document.createElement("td");
        statusCell.classList.add("nami-setup__availability-cell");
        for (const endpoint of ["source", "target"]) {
          const statusLayout = document.createElement("span");
          const dot = document.createElement("span");
          const statusText = document.createElement("span");
          statusLayout.classList.add("nami-setup__availability");
          statusLayout.dataset.endpoint = endpoint;
          dot.classList.add("nami-setup__availability-dot");
          dot.ariaHidden = "true";
          statusLayout.append(dot, statusText);
          statusCell.append(statusLayout);
          statuses[endpoint] = { layout: statusLayout, text: statusText };
        }
        row.append(paths, statusCell);
        select.addEventListener("click", () => handlers.onRecentPair(retained.pair));
        row.addEventListener("click", (event) => {
          if (event.target !== select && !select.contains(event.target) && !select.disabled) select.click();
        });
        retained = { row, select, sourcePath, targetPath, statuses, pair };
        recentRows.set(pair.mapping_id, retained);
      }
      retained.pair = pair;
      retained.row.dataset.sourceAvailability = states.source;
      retained.row.dataset.targetAvailability = states.target;
      retained.row.ariaDisabled = String(!editable || !online);
      retained.select.disabled = !editable || !online;
      renderFilesystemText(retained.sourcePath, pair.source.display);
      retained.sourcePath.title = pair.source.display;
      renderFilesystemText(retained.targetPath, pair.target.display);
      retained.targetPath.title = pair.target.display;
      retained.select.ariaLabel = `Select recent pair ${pair.source.display} to ${pair.target.display}`;
      for (const endpoint of ["source", "target"]) {
        retained.statuses[endpoint].layout.dataset.availability = states[endpoint];
        renderText(retained.statuses[endpoint].text, availabilityLabel(states[endpoint]));
      }
      if (recentBody.children[index] !== retained.row) {
        recentBody.insertBefore(retained.row, recentBody.children[index] ?? null);
      }
    });
    recentEmpty.hidden = values.length !== 0; recentTable.hidden = values.length === 0;
  }
  function renderFilters(values, editable) {
    filterList.replaceChildren();
    values.forEach((value, index) => {
      const item = document.createElement("li");
      const text = document.createElement("span");
      const remove = createButton("Remove");
      renderFilesystemText(text, value);
      remove.disabled = !editable;
      remove.addEventListener("click", () => handlers.onRemoveFilter(index));
      item.append(text, remove);
      filterList.append(item);
    });
    filterInput.disabled = !editable;
    addFilter.disabled = !editable;
  }

  function renderBatch(rows) {
    batch.replaceChildren();
    rows.forEach((value) => {
      const item = document.createElement("li");
      item.classList.add("nami-setup__batch-row");
      item.dataset.state = value.state;
      renderText(item, value.message);
      batch.append(item);
    });
    batch.hidden = rows.length === 0;
  }

  function renderPlanAgain(snapshot, mounts, editable) {
    planAgainChoices.replaceChildren();
    if (snapshot === null) return;
    for (const [purpose, state, candidates] of [
      ["source", snapshot.source_state, snapshot.source_candidates],
      ["target", snapshot.target_state, snapshot.target_candidates],
    ]) {
      if (state !== "ambiguous") continue;
      const group = document.createElement("div");
      const label = document.createElement("p");
      renderText(label, `Choose the current ${purpose} mount`);
      group.append(label);
      for (const candidate of candidates) {
        const button = createButton("", "nami-button nami-setup__mount");
        button.dataset.selected = String(mounts[purpose] === candidate);
        renderFilesystemText(button, candidate);
        button.disabled = !editable;
        button.addEventListener("click", () => handlers.onPlanAgainMount(purpose, candidate));
        group.append(button);
      }
      planAgainChoices.append(group);
    }
  }

  function render(model) {
    const setup = model.setup;
    if (setup === null) {
      root.hidden = true;
      return;
    }
    root.hidden = false;
    if (setup.setup_state === "frozen" && setup.task_kind === "sync-plan") {
      const message = model.artifactReady
        ? "Plan is ready. Plan again resolves the reviewed identities freshly."
        : model.sessionState === "active"
          ? "Planning is in progress. Reviewed folders and options are frozen."
          : "This plan's reviewed folders and options are frozen.";
      renderText(guidance, message);
    } else if (setup.task_kind === "inventory") {
      renderText(
        guidance,
        model.sessionState === "active"
          ? "Inventory is being created from the selected root."
          : "This inventory's reviewed root is frozen.",
      );
    } else {
      renderText(guidance, "Choose folders to create a reviewed plan or inventory task.");
    }
    const editable = model.editable;
    const locked = model.attempt !== null;
    const controlsEditable = editable && !locked && !model.batchRunning;
    const selectedMode = setup.task_kind ?? model.mode;
    const recents = setup.recents ?? { sources: [], targets: [], pairs: [] };
    const nextLocationContext = `${selectedMode}\u0000${controlsEditable}\u0000${model.source.text}\u0000${model.target.text}`;
    if (renderedModel !== null && (renderedModel !== model || locationContext !== nextLocationContext)) {
      const sourcePopupHadFocus = source.setOpen(false, false, true);
      const targetPopupHadFocus = target.setOpen(false, false, true);
      const popupHadFocus = sourcePopupHadFocus || targetPopupHadFocus;
      if (popupHadFocus && !controlsEditable) heading.focus();
    }
    renderedModel = model;
    locationContext = nextLocationContext;
    modeGroup.hidden = !editable;
    modeButtons.forEach((button, value) => {
      button.ariaChecked = String(value === selectedMode);
      button.tabIndex = value === selectedMode ? 0 : -1;
      button.disabled = !controlsEditable;
    });
    renderText(actionStatus, model.actionMessage ?? "");
    renderLocation(source, model.source, recents.sources, controlsEditable, selectedMode === "inventory" ? "Root" : "Source");
    renderLocation(target, model.target, recents.targets, controlsEditable, "Target");
    target.field.hidden = selectedMode === "inventory";
    recentCard.hidden = selectedMode === "inventory";
    renderRecentPairs(recents.pairs ?? [], model.recentPairAvailability, controlsEditable && selectedMode === "sync-plan");
    refreshRecents.disabled = !controlsEditable;
    const hasOptions = model.options !== null;
    options.hidden = !hasOptions || selectedMode === "inventory";
    moreSummary.ariaExpanded = String(moreExpanded);
    advancedOptions.hidden = !moreExpanded;
    if (hasOptions) {
      additive.input.checked = model.options.deletion_policy === "additive";
      optionInputs.forEach((input, key) => {
        input.checked = key in model.options ? model.options[key] : model.options.preservation[key];
      });
      renderFilters(model.options.filters, controlsEditable && selectedMode === "sync-plan");
    } else {
      renderFilters([], false);
    }
    additive.input.disabled = !controlsEditable || !hasOptions;
    optionInputs.forEach((input) => { input.disabled = !controlsEditable; });
    ads.input.disabled = true;
    const retryKind = typeof model.attempt?.retry === "function" && !model.attempt.running
      ? model.attempt.kind
      : null;
    const sourceNeedsMount = model.source.location?.state === "ambiguous";
    const targetNeedsMount = model.target.location?.state === "ambiguous";
    renderText(startPlan, retryKind === "sync-plan" ? "Retry plan start" : "Create plan");
    renderText(startInventory, retryKind === "inventory" ? "Retry inventory start" : "Create inventory");
    renderText(planAgain, retryKind === "plan-again" ? "Retry Plan again" : "Plan again");
    startPlan.hidden = selectedMode !== "sync-plan" || !editable;
    startPlan.disabled = retryKind === "sync-plan"
      ? model.batchRunning
      : !controlsEditable || !model.source.text || !model.target.text || sourceNeedsMount || targetNeedsMount;
    startInventory.hidden = selectedMode !== "inventory" || !editable;
    startInventory.disabled = retryKind === "inventory"
      ? model.batchRunning
      : !controlsEditable || !model.source.text || sourceNeedsMount;
    addPair.hidden = selectedMode !== "sync-plan" || !editable;
    addPair.disabled = !controlsEditable || model.batchRunning
      || (!model.source.text && !model.target.text)
      || model.batch.length >= MAX_BATCH_PAIRS;
    startBatch.hidden = selectedMode !== "sync-plan" || !editable;
    const retryableBatch = model.batch.some((row) => row.state === "uncertain");
    renderText(startBatch, retryableBatch ? "Retry pair batch" : "Create pair batch");
    startBatch.disabled = model.batchRunning || locked
      || model.batch.every((row) => !["queued", "uncertain"].includes(row.state));
    planAgain.hidden = !model.canPlanAgain;
    const unresolved = setup.plan_again !== null && [
      [setup.plan_again.source_state, model.planAgainMounts.source],
      [setup.plan_again.target_state, model.planAgainMounts.target],
    ].some(([state, mount]) => state === "ambiguous" && mount === null);
    planAgain.disabled = retryKind === "plan-again"
      ? model.batchRunning
      : !model.canPlanAgain || locked || model.batchRunning || unresolved;
    renderPlanAgain(setup.plan_again, model.planAgainMounts, !locked && !model.batchRunning);
    renderBatch(model.batch.slice(0, MAX_BATCH_PAIRS));
  }
  return Object.freeze({ element: root, render });
}
