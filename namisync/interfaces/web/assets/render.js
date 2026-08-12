export function renderText(element, text) {
  if (!(element instanceof Element)) {
    throw new TypeError("renderText target must be an Element");
  }
  if (typeof text !== "string") {
    throw new TypeError("renderText value must be a string");
  }
  element.textContent = text;
}
