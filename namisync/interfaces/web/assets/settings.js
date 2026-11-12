import { BridgeTransportError, commitSetupDefaults, readSetupDefaults } from "./bridge.js";
import { renderFilesystemText, renderText } from "./render.js";

function flatOptions(value) {
  return {
    filters: [...value.filters], deletion_policy: value.deletion_policy,
    trash_on_update: value.trash_on_update,
    preserve_created: value.preservation.preserve_created,
    preserve_acl: value.preservation.preserve_acl,
    propagate_source_casing: value.propagate_source_casing,
    verify_after_execute: value.verify_after_execute,
  };
}

function same(left, right) {
  return Array.isArray(left) ? left.length === right.length
    && left.every((value, index) => value === right[index]) : left === right;
}

export function installSetupDefaults(root) {
  const controls = root.querySelector("#setup-defaults-controls");
  const status = root.querySelector("#setup-defaults-status");
  const save = root.querySelector("#setup-defaults-save");
  const refresh = root.querySelector("#setup-defaults-refresh");
  if (![controls, status, save, refresh].every((value) => value instanceof HTMLElement)) {
    throw new TypeError("Setup defaults controls are unavailable");
  }
  const inputs = new Map();
  let baseline = null;
  let draft = null;
  let pending = null;
  let recovery = false;
  let saveUncertain = false;
  let message = "Open Settings to load Setup defaults.";

  const changed = () => baseline === null ? [] : Object.keys(baseline)
    .filter((key) => !same(draft[key], baseline[key]));
  const editable = () => baseline !== null && pending === null && !recovery;

  function toggle(key, caption, unavailable = false) {
    const label = document.createElement("label");
    label.className = "nami-toggle nami-settings__option";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.className = "nami-toggle__control";
    input.setAttribute("role", "switch");
    input.dataset.defaultOption = key;
    const text = document.createElement("span");
    renderText(text, caption);
    label.append(input, text);
    controls.append(label);
    if (unavailable) {
      input.disabled = true;
      label.title = "Alternate data stream preservation is unavailable.";
      return;
    }
    inputs.set(key, input);
    input.addEventListener("change", () => {
      if (!editable()) return;
      draft[key] = key === "deletion_policy" ? (input.checked ? "additive" : "trash") : input.checked;
      message = "";
      render();
    });
  }

  toggle("verify_after_execute", "Verify execution");
  toggle("deletion_policy", "Additive sync");
  toggle("trash_on_update", "Move replaced target files to trash");
  toggle("preserve_created", "Preserve creation time");
  toggle("preserve_acl", "Preserve access control lists");
  toggle("propagate_source_casing", "Use source casing");
  toggle("preserve_ads", "Preserve alternate data streams", true);

  const filters = document.createElement("div");
  filters.className = "nami-settings__filters";
  const filterLabel = document.createElement("label");
  filterLabel.htmlFor = "defaults-filter";
  renderText(filterLabel, "Exclude filters");
  const filterControls = document.createElement("div");
  filterControls.className = "nami-settings__filter-controls";
  const filterInput = document.createElement("input");
  filterInput.id = "defaults-filter";
  filterInput.className = "nami-input";
  filterInput.type = "text";
  filterInput.autocomplete = "off";
  filterInput.spellcheck = false;
  const add = document.createElement("button");
  add.type = "button";
  add.className = "nami-button";
  renderText(add, "Add filter");
  const list = document.createElement("ul");
  list.className = "nami-settings__filter-list";
  filterControls.append(filterInput, add);
  filters.append(filterLabel, filterControls, list);
  controls.append(filters);

  function addFilter() {
    if (!editable() || filterInput.value.length === 0) return;
    draft.filters.push(filterInput.value);
    filterInput.value = "";
    message = "";
    render();
  }
  add.addEventListener("click", addFilter);
  filterInput.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    addFilter();
  });

  function render() {
    const enabled = editable();
    for (const [key, input] of inputs) {
      input.disabled = !enabled;
      input.checked = key === "deletion_policy" ? draft?.[key] === "additive" : draft?.[key] === true;
    }
    filterInput.disabled = !enabled;
    add.disabled = !enabled;
    list.replaceChildren();
    for (const [index, value] of (draft?.filters ?? []).entries()) {
      const item = document.createElement("li");
      const text = document.createElement("span");
      renderFilesystemText(text, value);
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "nami-button";
      renderText(remove, "Remove");
      remove.disabled = !enabled;
      remove.addEventListener("click", () => {
        if (!editable()) return;
        draft.filters.splice(index, 1);
        message = "";
        render();
      });
      item.append(text, remove);
      list.append(item);
    }
    save.disabled = !enabled || changed().length === 0;
    refresh.hidden = !recovery;
    refresh.disabled = pending !== null;
    renderText(status, message || (changed().length > 0 ? "Unsaved changes." : ""));
    status.hidden = status.textContent.length === 0;
  }

  async function open() {
    if (pending !== null) return pending;
    const dirty = new Set(changed());
    const recovering = saveUncertain;
    message = "Reading Setup defaults…";
    pending = readSetupDefaults();
    render();
    try {
      const value = flatOptions(await pending);
      if (draft === null) draft = { ...value, filters: [...value.filters] };
      else for (const key of Object.keys(value)) {
        if (!dirty.has(key)) draft[key] = value[key];
      }
      baseline = value;
      recovery = false;
      saveUncertain = false;
      message = recovering ? "Current defaults loaded. The earlier save outcome could not be confirmed. Review your changes before saving." : "";
    } catch {
      message = "Defaults could not be read. Read current defaults to retry.";
      recovery = true;
    } finally {
      pending = null;
      render();
    }
  }

  async function saveDefaults() {
    if (!editable() || changed().length === 0) return;
    const patch = Object.fromEntries(changed().map((key) => [key,
      Array.isArray(draft[key]) ? [...draft[key]] : draft[key]]));
    message = "Saving defaults…";
    // Install the pending fence before invoking the bridge, including synchronous refusal.
    const attempt = Promise.resolve();
    pending = attempt;
    render();
    try {
      const result = await commitSetupDefaults(patch, () => {
        if (pending !== attempt) return;
        message = "Saving defaults is taking longer. Waiting for confirmation…";
        render();
      });
      baseline = flatOptions(result);
      draft = { ...baseline, filters: [...baseline.filters] };
      message = "Defaults saved. New tasks will use these choices.";
    } catch (error) {
      recovery = error instanceof BridgeTransportError;
      saveUncertain = recovery;
      message = recovery
        ? "Save outcome could not be confirmed. Read current defaults before saving again."
        : "Defaults were not saved. Check your filters and try Save defaults again.";
    } finally {
      pending = null;
      render();
    }
  }

  save.addEventListener("click", () => { void saveDefaults(); });
  refresh.addEventListener("click", () => { void open(); });
  render();
  return Object.freeze({ open });
}
