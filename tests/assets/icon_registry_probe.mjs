import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const [modulePath] = process.argv.slice(2);
if (!modulePath) {
  throw new Error("icons.js path is required");
}

const registry = await import(pathToFileURL(modulePath).href);
assert.deepEqual(Object.keys(registry).sort(), ["ICON_NAMES", "ICON_SIZES", "createIcon"]);
assert.deepEqual(registry.ICON_NAMES, [
  "checkmark-circle",
  "dismiss-circle",
  "warning",
  "info",
]);
assert.deepEqual(registry.ICON_SIZES, ["sm", "md", "lg"]);
assert.equal(Object.isFrozen(registry.ICON_NAMES), true);
assert.equal(Object.isFrozen(registry.ICON_SIZES), true);

const expectedGlyphClass = new Map([
  ["checkmark-circle", "nami-icon--checkmark-circle"],
  ["dismiss-circle", "nami-icon--dismiss-circle"],
  ["warning", "nami-icon--warning"],
  ["info", "nami-icon--info"],
]);

function fakeDocument() {
  const created = [];
  return {
    created,
    createElement(tagName) {
      const element = {
        ariaHidden: null,
        classes: [],
        classList: {
          add(...names) {
            element.classes.push(...names);
          },
        },
        tagName,
      };
      created.push(element);
      return element;
    },
  };
}

for (const glyph of registry.ICON_NAMES) {
  for (const size of registry.ICON_SIZES) {
    const document = fakeDocument();
    const icon = registry.createIcon(document, glyph, size);
    assert.equal(document.created.length, 1);
    assert.equal(icon.tagName, "span");
    assert.deepEqual(icon.classes, [
      "nami-icon",
      expectedGlyphClass.get(glyph),
      `nami-icon--${size}`,
    ]);
    assert.equal(icon.ariaHidden, "true");
  }
}

const invalidGlyphs = [
  "",
  "__proto__",
  "constructor",
  "toString",
  "INFO",
  "../info",
  "icons/info_20_regular.svg",
  "https://example.invalid/info.svg",
  null,
  1,
  {},
];
const invalidSizes = ["", "medium", "MD", "../md", "24px", null, 1, {}];

Object.defineProperty(Object.prototype, "inherited-glyph", {
  configurable: true,
  value: "nami-icon--warning",
});
try {
  const document = fakeDocument();
  assert.throws(
    () => registry.createIcon(document, "inherited-glyph", "md"),
    TypeError,
  );
  assert.equal(document.created.length, 0);
} finally {
  delete Object.prototype["inherited-glyph"];
}

for (const glyph of invalidGlyphs) {
  const document = fakeDocument();
  assert.throws(() => registry.createIcon(document, glyph, "md"), TypeError);
  assert.equal(document.created.length, 0);
}

for (const size of invalidSizes) {
  const document = fakeDocument();
  assert.throws(() => registry.createIcon(document, "info", size), TypeError);
  assert.equal(document.created.length, 0);
}

assert.throws(() => registry.createIcon(null, "info", "md"), TypeError);
