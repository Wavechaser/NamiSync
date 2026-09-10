import { renderFilesystemText, renderText } from "./render.js";

const MAX_BATCH_PAIRS = 48;

function requireCallback(value, name) {
  if (typeof value !== "function") {
    throw new TypeError(`${name} must be callable`);
  }
  return value;
}

function createButton(label, className = "nami-button") {
  const button = document.createElement("button");
  button.classList.add(...className.split(" "));
  button.type = "button";
  renderText(button, label);
  return button;
}

function createLocationRow(purpose, callbacks) {
  const field = document.createElement("div");
  field.classList.add("nami-field", "nami-setup__location");
  const label = document.createElement("label");
  const input = document.createElement("input");
  const status = document.createElement("p");
  const picker = createButton("Choose folder");
  const recents = document.createElement("div");
  const recentHeading = document.createElement("p");
  const recentList = document.createElement("div");
  const controls = document.createElement("div");

  field.dataset.purpose = purpose;
  input.classList.add("nami-input");
  input.type = "text";
  input.autocomplete = "off";
  input.spellcheck = false;
  input.id = `setup-${purpose}-path`;
  input.ariaDescribedBy = `setup-${purpose}-status`;
  label.htmlFor = input.id;
  renderText(label, purpose === "source" ? "Source folder" : "Target folder");
  status.classList.add("nami-field__hint", "nami-setup__location-status");
  status.id = `setup-${purpose}-status`;
  status.setAttribute("role", "status");
  recents.classList.add("nami-setup__recents");
  recentList.classList.add("nami-setup__recent-list");
  renderText(recentHeading, "Recent folders");
  controls.classList.add("nami-setup__location-controls");
  controls.append(picker);
  recents.append(recentHeading, recentList);
  field.append(label, input, controls, status, recents);

  const validate = () => callbacks.onValidate(purpose);
  input.addEventListener("input", () => callbacks.onEdit(purpose, input.value));
  input.addEventListener("blur", validate);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      validate();
    }
  });
  input.addEventListener("paste", () => {
    queueMicrotask(validate);
  });
  picker.addEventListener("click", () => callbacks.onPick(purpose));

  const mounts = document.createElement("div");
  mounts.classList.add("nami-setup__mounts");
  field.append(mounts);
  return { field, label, input, status, picker, recentList, mounts };
}

function locationStatus(location) {
  if (location === null || location === undefined) {
    return "Enter a folder path or choose a recent folder.";
  }
  if (location.state === "resolved") {
    return "Folder is ready.";
  }
  return location.detail ?? "That folder is not available.";
}

function replaceRecentRows(list, locations, onRecent, purpose, editable) {
  list.replaceChildren();
  for (const location of locations) {
    const button = createButton("", "nami-button nami-setup__recent");
    button.dataset.locationId = location.location_id;
    renderFilesystemText(button, location.display);
    button.disabled = !editable;
    button.addEventListener("click", () => onRecent(purpose, location));
    list.append(button);
  }
  list.hidden = locations.length === 0;
}

function createCheckbox(labelText, key, onOption) {
  const label = document.createElement("label");
  const input = document.createElement("input");
  const text = document.createElement("span");
  label.classList.add("nami-setup__option");
  input.classList.add("nami-checkbox");
  input.type = "checkbox";
  input.dataset.option = key;
  renderText(text, labelText);
  input.addEventListener("change", () => onOption(key, input.checked));
  label.append(input, text);
  return { label, input };
}

export function createSetupPanel(callbacks) {
  const handlers = {
    onEdit: requireCallback(callbacks?.onEdit, "onEdit"),
    onValidate: requireCallback(callbacks?.onValidate, "onValidate"),
    onPick: requireCallback(callbacks?.onPick, "onPick"),
    onRecent: requireCallback(callbacks?.onRecent, "onRecent"),
    onRecentPair: requireCallback(callbacks?.onRecentPair, "onRecentPair"),
    onMode: requireCallback(callbacks?.onMode, "onMode"),
    onOption: requireCallback(callbacks?.onOption, "onOption"),
    onAddFilter: requireCallback(callbacks?.onAddFilter, "onAddFilter"),
    onRemoveFilter: requireCallback(callbacks?.onRemoveFilter, "onRemoveFilter"),
    onMount: requireCallback(callbacks?.onMount, "onMount"),
    onPlanAgainMount: requireCallback(callbacks?.onPlanAgainMount, "onPlanAgainMount"),
    onStartPlan: requireCallback(callbacks?.onStartPlan, "onStartPlan"),
    onStartInventory: requireCallback(callbacks?.onStartInventory, "onStartInventory"),
    onAddPair: requireCallback(callbacks?.onAddPair, "onAddPair"),
    onStartBatch: requireCallback(callbacks?.onStartBatch, "onStartBatch"),
    onPlanAgain: requireCallback(callbacks?.onPlanAgain, "onPlanAgain"),
  };
  const root = document.createElement("div");
  const heading = document.createElement("h3");
  const guidance = document.createElement("p");
  const actionStatus = document.createElement("p");
  const modeLabel = document.createElement("label");
  const mode = document.createElement("select");
  const options = document.createElement("fieldset");
  const optionLegend = document.createElement("legend");
  const policy = document.createElement("select");
  const policyLabel = document.createElement("label");
  const optionsList = document.createElement("div");
  const filters = document.createElement("div");
  const filterLabel = document.createElement("label");
  const filterInput = document.createElement("input");
  const addFilter = createButton("Add filter");
  const filterList = document.createElement("ul");
  const actionRow = document.createElement("div");
  const startPlan = createButton("Create plan", "nami-button nami-button--primary");
  const startInventory = createButton("Create inventory");
  const addPair = createButton("Add pair");
  const startBatch = createButton("Create pair batch", "nami-button nami-button--primary");
  const planAgain = createButton("Plan again");
  const planAgainChoices = document.createElement("div");
  const batch = document.createElement("ol");
  const recentPairs = document.createElement("div");
  const recentPairsHeading = document.createElement("p");
  const recentPairsList = document.createElement("div");
  const source = createLocationRow("source", handlers);
  const target = createLocationRow("target", handlers);

  root.classList.add("nami-work-panel__setup", "nami-setup");
  renderText(heading, "Setup");
  renderText(guidance, "Choose folders to create a reviewed plan or inventory task.");
  actionStatus.classList.add("nami-field__hint", "nami-setup__action-status");
  actionStatus.setAttribute("role", "status");
  modeLabel.htmlFor = "setup-task-type";
  renderText(modeLabel, "Task type");
  mode.classList.add("nami-select", "nami-setup__mode");
  mode.id = "setup-task-type";
  for (const [value, label] of [["sync-plan", "Sync plan"], ["inventory", "Inventory"]]) {
    const option = document.createElement("option");
    option.value = value;
    renderText(option, label);
    mode.append(option);
  }
  mode.addEventListener("change", () => handlers.onMode(mode.value));
  options.classList.add("nami-setup__options");
  renderText(optionLegend, "Plan options");
  policyLabel.htmlFor = "setup-deletion-policy";
  renderText(policyLabel, "Deletion policy");
  policy.classList.add("nami-select");
  policy.id = "setup-deletion-policy";
  for (const [value, label] of [["trash", "Move removed files to trash"], ["additive", "Keep target-only files"]]) {
    const option = document.createElement("option");
    option.value = value;
    renderText(option, label);
    policy.append(option);
  }
  policy.addEventListener("change", () => handlers.onOption("deletion_policy", policy.value));
  filterLabel.htmlFor = "setup-filter";
  renderText(filterLabel, "Exclude filters");
  filterInput.classList.add("nami-input");
  filterInput.id = "setup-filter";
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
  filterList.classList.add("nami-setup__filter-list");
  filters.append(filterLabel, filterInput, addFilter, filterList);
  optionsList.classList.add("nami-setup__options-list");
  const optionInputs = new Map();
  for (const [key, label] of [
    ["trash_on_update", "Move replaced target files to trash"],
    ["preserve_created", "Preserve creation time"],
    ["preserve_acl", "Preserve access control lists"],
    ["propagate_source_casing", "Use source casing"],
    ["verify_after_execute", "Verify after copying"],
  ]) {
    const checkbox = createCheckbox(label, key, handlers.onOption);
    optionInputs.set(key, checkbox.input);
    optionsList.append(checkbox.label);
  }
  const ads = createCheckbox("Preserve alternate data streams", "preserve_ads", handlers.onOption);
  ads.input.checked = false;
  ads.input.disabled = true;
  ads.label.title = "Alternate data stream preservation is unavailable.";
  optionsList.append(ads.label);
  options.append(optionLegend, policyLabel, policy, filters, optionsList);
  actionRow.classList.add("nami-setup__actions");
  batch.classList.add("nami-setup__batch");
  batch.ariaLabel = "Pair creation results";
  actionRow.append(startPlan, startInventory, addPair, startBatch, planAgain);
  planAgainChoices.classList.add("nami-setup__plan-again-mounts");
  recentPairs.classList.add("nami-setup__recent-pairs");
  recentPairsList.classList.add("nami-setup__recent-pair-list");
  renderText(recentPairsHeading, "Recent pairs");
  recentPairs.append(recentPairsHeading, recentPairsList);
  root.append(
    heading, guidance, actionStatus, modeLabel, mode, source.field, target.field,
    recentPairs, options, actionRow, planAgainChoices, batch,
  );

  startPlan.addEventListener("click", () => handlers.onStartPlan());
  startInventory.addEventListener("click", () => handlers.onStartInventory());
  addPair.addEventListener("click", () => handlers.onAddPair());
  startBatch.addEventListener("click", () => handlers.onStartBatch());
  planAgain.addEventListener("click", () => handlers.onPlanAgain());

  function renderLocation(row, value, recents, editable, label) {
    const focused = document.activeElement === row.input;
    if (!focused && row.input.value !== value.text) {
      row.input.value = value.text;
    }
    row.input.dataset.state = value.location?.state ?? "unresolved";
    renderText(row.status, locationStatus(value.location));
    replaceRecentRows(row.recentList, recents, handlers.onRecent, row.field.dataset.purpose, editable);
    row.label.htmlFor = row.input.id;
    renderText(row.label, label);
    row.mounts.replaceChildren();
    const mountCandidates = value.location?.state === "ambiguous"
      && (typeof value.continuationId === "string" || value.candidate !== null)
      ? value.location.candidates
      : [];
    mountCandidates.forEach((candidate, index) => {
      const mount = createButton("", "nami-button nami-setup__mount");
      mount.dataset.mountIndex = String(index);
      mount.dataset.selected = value.mountIndex === index ? "true" : "false";
      mount.ariaPressed = value.mountIndex === index ? "true" : "false";
      renderFilesystemText(mount, candidate);
      mount.disabled = !editable;
      mount.addEventListener("click", () => handlers.onMount(row.field.dataset.purpose, index));
      row.mounts.append(mount);
    });
    row.picker.disabled = !editable;
  }

  function renderRecentPairs(values, editable) {
    recentPairsList.replaceChildren();
    for (const pair of values) {
      const button = createButton("", "nami-button nami-setup__recent-pair");
      const sourceText = document.createElement("span");
      const separator = document.createElement("span");
      const targetText = document.createElement("span");
      button.dataset.mappingId = pair.mapping_id;
      renderFilesystemText(sourceText, pair.source.display);
      renderText(separator, " → ");
      renderFilesystemText(targetText, pair.target.display);
      button.append(sourceText, separator, targetText);
      button.disabled = !editable;
      button.addEventListener("click", () => handlers.onRecentPair(pair));
      recentPairsList.append(button);
    }
    recentPairs.hidden = values.length === 0;
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
    for (const row of rows) {
      const item = document.createElement("li");
      item.classList.add("nami-setup__batch-row");
      item.dataset.state = row.state;
      renderText(item, row.message);
      batch.append(item);
    }
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
        button.dataset.selected = mounts[purpose] === candidate ? "true" : "false";
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
    const recents = setup.recents ?? { sources: [], targets: [] };
    if (document.activeElement !== mode) mode.value = selectedMode;
    modeLabel.hidden = !editable;
    mode.hidden = !editable;
    mode.disabled = !controlsEditable;
    renderText(actionStatus, model.actionMessage ?? "");
    renderLocation(source, model.source, recents.sources, controlsEditable, selectedMode === "inventory" ? "Inventory root" : "Source folder");
    renderLocation(target, model.target, recents.targets, controlsEditable, "Target folder");
    target.field.hidden = selectedMode === "inventory";
    renderRecentPairs(recents.pairs ?? [], controlsEditable && selectedMode === "sync-plan");
    if (selectedMode === "inventory") recentPairs.hidden = true;
    const hasOptions = model.options !== null;
    options.hidden = !hasOptions || selectedMode === "inventory";
    if (hasOptions && document.activeElement !== policy) {
      policy.value = model.options.deletion_policy;
    }
    if (hasOptions) {
      for (const [key, input] of optionInputs) {
        input.checked = key in model.options
          ? model.options[key]
          : model.options.preservation[key];
      }
      renderFilters(model.options.filters, controlsEditable && selectedMode === "sync-plan");
    } else {
      renderFilters([], false);
    }
    source.input.disabled = !controlsEditable;
    target.input.disabled = !controlsEditable;
    policy.disabled = !controlsEditable || !hasOptions;
    for (const input of optionInputs.values()) input.disabled = !controlsEditable;
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
    addPair.disabled = !controlsEditable || model.batchRunning ||
      (!model.source.text && !model.target.text) || model.batch.length >= MAX_BATCH_PAIRS;
    startBatch.hidden = selectedMode !== "sync-plan" || !editable;
    const retryableBatch = model.batch.some((row) => row.state === "uncertain");
    renderText(startBatch, retryableBatch ? "Retry pair batch" : "Create pair batch");
    startBatch.disabled = model.batchRunning || locked ||
      model.batch.every((row) => !["queued", "uncertain"].includes(row.state));
    planAgain.hidden = !model.canPlanAgain;
    const unresolvedPlanAgain = setup.plan_again !== null && [
      [setup.plan_again.source_state, model.planAgainMounts.source],
      [setup.plan_again.target_state, model.planAgainMounts.target],
    ].some(([state, mount]) => state === "ambiguous" && mount === null);
    planAgain.disabled = retryKind === "plan-again"
      ? model.batchRunning
      : !model.canPlanAgain || locked || model.batchRunning || unresolvedPlanAgain;
    renderPlanAgain(setup.plan_again, model.planAgainMounts, !locked && !model.batchRunning);
    renderBatch(model.batch.slice(0, MAX_BATCH_PAIRS));
  }

  return Object.freeze({ element: root, render });
}
