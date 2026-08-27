import {
  BridgeTransportError,
  readCosmeticSection,
  replaceCosmeticSection,
} from "./bridge.js";
import { renderText } from "./render.js";

const THEMES = Object.freeze(["system", "light", "dark"]);
const VIEWPORT_INSET = 8;

function isTheme(value) {
  return typeof value === "string" && THEMES.includes(value);
}

export function installThemeCombobox(root) {
  if (!(root instanceof HTMLElement)) {
    throw new TypeError("Theme combobox root must be an HTML element");
  }
  const trigger = root.querySelector(".nami-combobox__trigger");
  const popupId = trigger?.getAttribute("aria-controls");
  const popup = popupId === null ? null : document.getElementById(popupId);
  const valueElement = trigger?.querySelector("span");
  const options = popup === null
    ? []
    : [...popup.querySelectorAll('.nami-combobox__option[data-value]')];
  if (
    !(trigger instanceof HTMLButtonElement)
    || !(popup instanceof HTMLElement)
    || !(valueElement instanceof HTMLElement)
    || options.length !== THEMES.length
    || !options.every((option) => (
      option instanceof HTMLElement && isTheme(option.dataset.value)
    ))
    || new Set(options.map((option) => option.dataset.value)).size !== THEMES.length
  ) {
    throw new TypeError("Theme combobox structure is unavailable");
  }

  let value = isTheme(root.dataset.value) ? root.dataset.value : "system";
  let disabled = trigger.disabled;
  let activeValue = value;

  const optionFor = (theme) => options.find(
    (option) => option.dataset.value === theme,
  );
  const setActiveDescendant = (option) => {
    trigger.setAttribute("aria-activedescendant", option.id);
  };

  const renderValue = (theme) => {
    const selected = optionFor(theme);
    if (selected === undefined) {
      throw new TypeError("Theme combobox value is invalid");
    }
    value = theme;
    root.dataset.value = theme;
    renderText(valueElement, selected.textContent.trim());
    for (const option of options) {
      const current = option === selected;
      option.ariaSelected = String(current);
    }
    setActiveDescendant(selected);
  };

  const renderActive = (theme, visible = true) => {
    activeValue = theme;
    for (const option of options) {
      option.toggleAttribute(
        "data-active",
        visible && option.dataset.value === theme,
      );
    }
    const active = optionFor(theme);
    if (active !== undefined) {
      setActiveDescendant(active);
    }
  };

  const positionPopup = () => {
    if (popup.hidden) {
      return;
    }
    const triggerBounds = trigger.getBoundingClientRect();
    popup.style.inlineSize = `${triggerBounds.width}px`;
    const selected = optionFor(value);
    if (selected === undefined) {
      return;
    }
    const popupBounds = popup.getBoundingClientRect();
    const selectedCenter = selected.offsetTop + selected.offsetHeight / 2;
    const desiredTop = triggerBounds.top + triggerBounds.height / 2 - selectedCenter;
    const maximumTop = Math.max(
      VIEWPORT_INSET,
      window.innerHeight - popupBounds.height - VIEWPORT_INSET,
    );
    const maximumLeft = Math.max(
      VIEWPORT_INSET,
      window.innerWidth - popupBounds.width - VIEWPORT_INSET,
    );
    popup.style.insetBlockStart = `${Math.min(maximumTop, Math.max(VIEWPORT_INSET, desiredTop))}px`;
    popup.style.insetInlineStart = `${Math.min(maximumLeft, Math.max(VIEWPORT_INSET, triggerBounds.left))}px`;
  };

  const closePopup = () => {
    popup.hidden = true;
    popup.style.removeProperty("visibility");
    trigger.ariaExpanded = "false";
    renderActive(value, false);
  };

  const openPopup = () => {
    if (disabled) {
      return;
    }
    renderActive(value, false);
    popup.style.visibility = "hidden";
    popup.hidden = false;
    trigger.ariaExpanded = "true";
    positionPopup();
    popup.style.removeProperty("visibility");
  };

  const choose = (theme) => {
    if (disabled || !isTheme(theme)) {
      return;
    }
    renderValue(theme);
    closePopup();
    root.dispatchEvent(new Event("change", { bubbles: true }));
  };

  trigger.addEventListener("click", () => {
    if (popup.hidden) {
      openPopup();
    } else {
      closePopup();
    }
  });
  trigger.addEventListener("keydown", (event) => {
    if (disabled) {
      return;
    }
    if (event.key === "Tab") {
      closePopup();
      return;
    }
    if (event.key === "Escape") {
      if (!popup.hidden) {
        event.preventDefault();
        closePopup();
      }
      return;
    }
    if (!new Set(["ArrowDown", "ArrowUp", "Enter", " "]).has(event.key)) {
      return;
    }
    event.preventDefault();
    if (popup.hidden) {
      openPopup();
      return;
    }
    if (event.key === "Enter" || event.key === " ") {
      choose(activeValue);
      return;
    }
    const index = THEMES.indexOf(activeValue);
    const direction = event.key === "ArrowDown" ? 1 : -1;
    renderActive(THEMES[(index + direction + THEMES.length) % THEMES.length]);
  });
  for (const option of options) {
    option.addEventListener("pointermove", () => {
      renderActive(option.dataset.value);
    });
    option.addEventListener("click", () => {
      choose(option.dataset.value);
      trigger.focus();
    });
  }
  document.addEventListener("pointerdown", (event) => {
    if (
      !popup.hidden
      && !root.contains(event.target)
      && !popup.contains(event.target)
    ) {
      closePopup();
    }
  });
  window.addEventListener("resize", positionPopup);
  window.addEventListener("scroll", positionPopup, true);

  renderValue(value);
  closePopup();
  return Object.freeze({
    addEventListener(name, callback) {
      root.addEventListener(name, callback);
    },
    removeEventListener(name, callback) {
      root.removeEventListener(name, callback);
    },
    get disabled() {
      return disabled;
    },
    set disabled(next) {
      disabled = Boolean(next);
      trigger.disabled = disabled;
      root.ariaDisabled = String(disabled);
      if (disabled) {
        closePopup();
      }
    },
    get value() {
      return value;
    },
    set value(next) {
      if (!isTheme(next)) {
        throw new TypeError("Theme combobox value is invalid");
      }
      renderValue(next);
    },
  });
}

export function installThemeSelector(
  select,
  {
    read = readCosmeticSection,
    replace = replaceCosmeticSection,
  } = {},
) {
  if (
    select === null
    || typeof select !== "object"
    || typeof select.value !== "string"
    || typeof select.disabled !== "boolean"
    || typeof select.addEventListener !== "function"
    || typeof select.removeEventListener !== "function"
  ) {
    throw new TypeError("Theme selector must expose a control interface");
  }
  if (typeof read !== "function" || typeof replace !== "function") {
    throw new TypeError("Theme selector commands must be callable");
  }

  let generation = 0;
  let current = null;
  let renderedTheme = "system";
  let closed = false;
  let replacementSettlement = Promise.resolve();
  let replacementPending = false;
  let unresolvedRevision = null;

  select.disabled = true;

  const isCurrent = (state) => (
    !closed && current === state && state?.generation === generation
  );

  const renderAuthoritative = (state) => {
    select.value = state?.authoritative?.value.theme ?? renderedTheme;
  };

  const accept = (state, snapshot) => {
    if (!isCurrent(state)) {
      return false;
    }
    if (
      state.authoritative !== null
      && (
        snapshot.revision < state.authoritative.revision
        || (
          snapshot.revision === state.authoritative.revision
          && snapshot.value.theme !== state.authoritative.value.theme
        )
      )
    ) {
      return false;
    }
    state.authoritative = snapshot;
    renderedTheme = snapshot.value.theme;
    renderAuthoritative(state);
    return true;
  };

  const observeRevision = (revision) => {
    if (unresolvedRevision !== null && revision > unresolvedRevision) {
      unresolvedRevision = null;
    }
  };

  const reconcileAfterUncertainty = async (state, expectedRevision) => {
    try {
      const snapshot = await read();
      observeRevision(snapshot.revision);
      const accepted = accept(state, snapshot);
      return accepted && snapshot.revision > expectedRevision;
    } catch {
      return false;
    }
  };

  const replaceDesiredThemes = async (state) => {
    state.replacing = true;
    let recoverable = true;
    try {
      while (isCurrent(state) && state.desiredTheme !== null) {
        const theme = state.desiredTheme;
        state.desiredTheme = null;
        if (theme === state.authoritative.value.theme) {
          continue;
        }

        let result;
        const expectedRevision = state.authoritative.revision;
        try {
          result = await replace(expectedRevision, theme);
        } catch (error) {
          state.desiredTheme = null;
          if (error instanceof BridgeTransportError) {
            unresolvedRevision = Math.max(
              unresolvedRevision ?? expectedRevision,
              expectedRevision,
            );
            recoverable = await reconcileAfterUncertainty(
              state,
              expectedRevision,
            );
          } else {
            recoverable = false;
          }
          state.desiredTheme = null;
          break;
        }
        observeRevision(result.revision);
        if (!accept(state, result)) {
          recoverable = false;
          state.desiredTheme = null;
          break;
        }
        if (result.disposition === "conflict") {
          state.desiredTheme = null;
          break;
        }
      }
    } finally {
      state.replacing = false;
      if (isCurrent(state)) {
        renderAuthoritative(state);
        select.disabled = !recoverable;
      }
    }
  };

  const onChange = () => {
    const state = current;
    const requestedTheme = select.value;
    renderAuthoritative(state);
    if (
      !isCurrent(state)
      || state.authoritative === null
      || !isTheme(requestedTheme)
    ) {
      if (state !== null) {
        state.desiredTheme = null;
      }
      select.disabled = true;
      return;
    }
    state.desiredTheme = requestedTheme;
    select.disabled = true;
    if (!state.replacing) {
      const settlement = replaceDesiredThemes(state);
      replacementSettlement = settlement;
      replacementPending = true;
      void settlement.then(
        () => {
          if (replacementSettlement === settlement) {
            replacementPending = false;
          }
        },
        () => {
          if (replacementSettlement === settlement) {
            replacementPending = false;
          }
        },
      );
    }
  };

  select.addEventListener("change", onChange);

  const invalidate = () => {
    generation += 1;
    current = null;
    renderAuthoritative(null);
    select.disabled = true;
  };

  const open = async (appliedPresentationRevision = null) => {
    if (closed) {
      return false;
    }
    invalidate();
    const state = {
      authoritative: null,
      desiredTheme: null,
      generation,
      replacing: false,
    };
    current = state;
    try {
      if (replacementPending) {
        await replacementSettlement;
        if (!isCurrent(state)) {
          return false;
        }
      }
      const snapshot = await read(appliedPresentationRevision);
      observeRevision(snapshot.revision);
      if (!accept(state, snapshot)) {
        return false;
      }
      if (
        unresolvedRevision !== null
        && snapshot.revision <= unresolvedRevision
      ) {
        return false;
      }
      select.disabled = false;
      return true;
    } catch {
      return false;
    }
  };

  return Object.freeze({
    close() {
      if (closed) {
        return;
      }
      closed = true;
      generation += 1;
      current = null;
      select.disabled = true;
      select.removeEventListener("change", onChange);
    },
    invalidate,
    open,
    async refresh(appliedPresentationRevision = null) {
      if (closed || current === null) {
        return false;
      }
      return open(appliedPresentationRevision);
    },
  });
}
