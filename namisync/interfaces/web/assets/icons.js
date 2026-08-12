const GLYPH_CLASSES = Object.freeze({
  "checkmark-circle": "nami-icon--checkmark-circle",
  "dismiss-circle": "nami-icon--dismiss-circle",
  warning: "nami-icon--warning",
  info: "nami-icon--info",
});

const SIZE_CLASSES = Object.freeze({
  sm: "nami-icon--sm",
  md: "nami-icon--md",
  lg: "nami-icon--lg",
});

export const ICON_NAMES = Object.freeze(Object.keys(GLYPH_CLASSES));
export const ICON_SIZES = Object.freeze(Object.keys(SIZE_CLASSES));

export function createIcon(document, glyph, size = "md") {
  if (
    typeof glyph !== "string" ||
    !Object.hasOwn(GLYPH_CLASSES, glyph) ||
    typeof size !== "string" ||
    !Object.hasOwn(SIZE_CLASSES, size)
  ) {
    throw new TypeError("icon glyph and size must be registered");
  }
  if (document === null || typeof document?.createElement !== "function") {
    throw new TypeError("icon document must create elements");
  }

  const icon = document.createElement("span");
  icon.classList.add("nami-icon", GLYPH_CLASSES[glyph], SIZE_CLASSES[size]);
  icon.ariaHidden = "true";
  return icon;
}
