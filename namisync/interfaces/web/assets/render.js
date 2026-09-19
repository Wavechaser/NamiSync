export function renderText(element, text) {
  if (!(element instanceof Element)) {
    throw new TypeError("renderText target must be an Element");
  }
  if (typeof text !== "string") {
    throw new TypeError("renderText value must be a string");
  }
  element.textContent = text;
}

const BYTE_UNITS = Object.freeze(["B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB"]);

function byteCountInteger(value) {
  if (typeof value === "bigint") {
    if (value < 0n) throw new RangeError("byte count must be non-negative");
    return value;
  }
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value) || value < 0) {
      throw new RangeError("byte count must be a non-negative safe integer");
    }
    return BigInt(value);
  }
  if (typeof value !== "string" || !/^\d+$/.test(value)) {
    throw new TypeError("byte count must be a decimal integer");
  }
  return BigInt(value);
}

export function formatByteCount(value) {
  const bytes = byteCountInteger(value);
  let unitIndex = 0;
  let unit = 1n;
  while (unitIndex < BYTE_UNITS.length - 1 && bytes >= unit * 1024n) {
    unit *= 1024n;
    unitIndex += 1;
  }
  if (unitIndex === 0) return `${bytes} B`;

  while (true) {
    const scale = 100n;
    const rounded = (bytes * scale + unit / 2n) / unit;
    const integer = rounded / scale;

    if (rounded >= 1024n * scale && unitIndex < BYTE_UNITS.length - 1) {
      unit *= 1024n;
      unitIndex += 1;
      continue;
    }

    const fraction = `.${(rounded % scale).toString().padStart(2, "0")}`;
    return `${integer}${fraction} ${BYTE_UNITS[unitIndex]}`;
  }
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
