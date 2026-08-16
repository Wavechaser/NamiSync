export function renderText(element, text) {
  if (!(element instanceof Element)) {
    throw new TypeError("renderText target must be an Element");
  }
  if (typeof text !== "string") {
    throw new TypeError("renderText value must be a string");
  }
  element.textContent = text;
}

const FILESYSTEM_LAYOUT_CONTROL =
  /[\u0000-\u001f\u007f-\u009f\u00ad\u061c\u200b\u200e-\u200f\u2028-\u202e\u2060-\u206f\ufeff\u27e6-\u27e7]/gu;

export function renderFilesystemText(element, text) {
  if (typeof text !== "string") {
    throw new TypeError("renderFilesystemText value must be a string");
  }
  const visibleText = text.replace(FILESYSTEM_LAYOUT_CONTROL, (character) =>
    `⟦U+${character.codePointAt(0).toString(16).toUpperCase().padStart(4, "0")}⟧`
  );
  renderText(element, visibleText);
}
