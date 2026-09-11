// BEGIN GENERATED ICON REGISTRY
const GLYPH_CLASSES = Object.freeze({
  "add": "nami-icon--add",
  "add-circle": "nami-icon--add-circle",
  "add-square-multiple": "nami-icon--add-square-multiple",
  "approvals-app": "nami-icon--approvals-app",
  "archive-clock": "nami-icon--archive-clock",
  "arrow-clockwise": "nami-icon--arrow-clockwise",
  "arrow-sync": "nami-icon--arrow-sync",
  "arrow-sync-checkmark": "nami-icon--arrow-sync-checkmark",
  "checkmark": "nami-icon--checkmark",
  "checkmark-circle": "nami-icon--checkmark-circle",
  "clipboard-paste": "nami-icon--clipboard-paste",
  "copy": "nami-icon--copy",
  "database-arrow-up": "nami-icon--database-arrow-up",
  "database-checkmark": "nami-icon--database-checkmark",
  "delete": "nami-icon--delete",
  "dismiss": "nami-icon--dismiss",
  "dismiss-circle": "nami-icon--dismiss-circle",
  "error-circle": "nami-icon--error-circle",
  "eye": "nami-icon--eye",
  "folder": "nami-icon--folder",
  "folder-holder": "nami-icon--folder-holder",
  "folder-open": "nami-icon--folder-open",
  "history": "nami-icon--history",
  "info": "nami-icon--info",
  "location": "nami-icon--location",
  "location-ripple": "nami-icon--location-ripple",
  "more-horizontal": "nami-icon--more-horizontal",
  "more-vertical": "nami-icon--more-vertical",
  "navigation": "nami-icon--navigation",
  "pause": "nami-icon--pause",
  "pause-circle": "nami-icon--pause-circle",
  "pin": "nami-icon--pin",
  "pin-off": "nami-icon--pin-off",
  "play": "nami-icon--play",
  "play-circle": "nami-icon--play-circle",
  "prohibited": "nami-icon--prohibited",
  "question-circle": "nami-icon--question-circle",
  "record-stop": "nami-icon--record-stop",
  "replay": "nami-icon--replay",
  "save": "nami-icon--save",
  "scan-dash": "nami-icon--scan-dash",
  "search": "nami-icon--search",
  "settings": "nami-icon--settings",
  "shifts-activity": "nami-icon--shifts-activity",
  "subtract": "nami-icon--subtract",
  "subtract-circle": "nami-icon--subtract-circle",
  "timeline": "nami-icon--timeline",
  "warning": "nami-icon--warning",
});
// END GENERATED ICON REGISTRY

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
    !Object.prototype.hasOwnProperty.call(GLYPH_CLASSES, glyph) ||
    typeof size !== "string" ||
    !Object.prototype.hasOwnProperty.call(SIZE_CLASSES, size)
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
