const MESSAGE_KIND = "namisync.appearance.v2";
const OPAQUE_COLOR = /^#[0-9A-F]{6}$/;
const ALPHA_COLOR = /^#[0-9A-F]{8}$/;
const KEYS = Object.freeze([
  "accentFill",
  "accentFillForeground",
  "accentFillHover",
  "accentFillPressed",
  "highContrast",
  "kind",
  "material",
  "revision",
  "theme",
]);

function isExactObject(value) {
  if (
    value === null
    || typeof value !== "object"
    || Array.isArray(value)
    || Object.getPrototypeOf(value) !== Object.prototype
  ) {
    return false;
  }
  const keys = Object.keys(value).sort();
  return keys.length === KEYS.length && keys.every((key, index) => key === KEYS[index]);
}

function isAppearanceMessage(value, previousRevision) {
  return isExactObject(value)
    && value.kind === MESSAGE_KIND
    && Number.isSafeInteger(value.revision)
    && value.revision > previousRevision
    && (value.theme === "light" || value.theme === "dark")
    && typeof value.highContrast === "boolean"
    && (
      value.material === "mica"
      || value.material === "opaque"
      || value.material === "degraded"
    )
    && OPAQUE_COLOR.test(value.accentFill)
    && ALPHA_COLOR.test(value.accentFillHover)
    && ALPHA_COLOR.test(value.accentFillPressed)
    && OPAQUE_COLOR.test(value.accentFillForeground);
}

export function installAppearanceReceiver(webview, root, onApplied = null) {
  if (webview === null || typeof webview !== "object") {
    throw new TypeError("WebView2 appearance receiver is unavailable");
  }
  if (!(root instanceof HTMLElement)) {
    throw new TypeError("Appearance root must be an HTML element");
  }
  if (onApplied !== null && typeof onApplied !== "function") {
    throw new TypeError("Appearance observer must be callable");
  }

  let revision = 0;
  let applicationWaiters = [];
  const receive = (event) => {
    const value = event.data;
    if (!isAppearanceMessage(value, revision)) {
      return;
    }

    root.dataset.theme = value.theme;
    root.dataset.highContrast = String(value.highContrast);
    root.dataset.windowMaterial = value.material;
    root.style.setProperty("--color-accent-fill", value.accentFill);
    root.style.setProperty("--color-accent-fill-hover", value.accentFillHover);
    root.style.setProperty("--color-accent-fill-pressed", value.accentFillPressed);
    root.style.setProperty(
      "--color-accent-fill-foreground",
      value.accentFillForeground,
    );
    revision = value.revision;
    const ready = applicationWaiters.filter(
      (waiter) => revision > waiter.previousRevision,
    );
    applicationWaiters = applicationWaiters.filter(
      (waiter) => revision <= waiter.previousRevision,
    );
    for (const waiter of ready) waiter.resolve();
    if (onApplied !== null) {
      try {
        onApplied();
      } catch {
        // Appearance application remains independently degradable.
      }
    }
  };

  const whenAppliedAfter = (previousRevision) => {
    if (
      !Number.isSafeInteger(previousRevision)
      || previousRevision < 0
      || previousRevision > revision
    ) {
      throw new TypeError("Appearance baseline revision is invalid");
    }
    if (revision > previousRevision) {
      return Promise.resolve();
    }
    const existing = applicationWaiters.find(
      (waiter) => waiter.previousRevision === previousRevision,
    );
    if (existing !== undefined) {
      return existing.promise;
    }
    let resolveApplication;
    const promise = new Promise((resolve) => {
      resolveApplication = resolve;
    });
    applicationWaiters.push({
      previousRevision,
      promise,
      resolve: resolveApplication,
    });
    return promise;
  };

  webview.addEventListener("message", receive);
  return Object.freeze({
    close() {
      webview.removeEventListener("message", receive);
    },
    revision() {
      return revision;
    },
    whenApplied() {
      return whenAppliedAfter(0);
    },
    whenAppliedAfter,
  });
}
