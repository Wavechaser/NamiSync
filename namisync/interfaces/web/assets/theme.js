import {
  BridgeTransportError,
  readCosmeticSection,
  replaceCosmeticSection,
} from "./bridge.js";

const THEMES = Object.freeze(["system", "light", "dark"]);

function isTheme(value) {
  return typeof value === "string" && THEMES.includes(value);
}

export function installThemeSelector(
  select,
  {
    read = readCosmeticSection,
    replace = replaceCosmeticSection,
  } = {},
) {
  if (!(select instanceof HTMLSelectElement)) {
    throw new TypeError("Theme selector must be a select element");
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

  const open = async () => {
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
      const snapshot = await read();
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
    async refresh() {
      if (closed || current === null) {
        return false;
      }
      return open();
    },
  });
}
