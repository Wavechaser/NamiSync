import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";


let setterCalls = 0;

class TestElement {
  constructor() {
    this.value = "";
  }

  get textContent() {
    return this.value;
  }

  set textContent(value) {
    setterCalls += 1;
    assert.equal(typeof value, "string");
    this.value = value;
  }
}

globalThis.Element = TestElement;

const modulePath = process.argv[2];
assert.ok(modulePath, "render module path is required");
const source = await readFile(modulePath, "utf8");
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const { formatFilesystemPath, renderFilesystemText, renderText } = await import(moduleUrl);

for (const [root, path, expected] of [
  ["D:\\Target", "Case\\File.txt", "D:\\Target\\Case\\File.txt"],
  ["D:\\", "File.txt", "D:\\File.txt"],
  ["D:\\Target\\", "File.txt", "D:\\Target\\File.txt"],
  ["\\\\server\\share", "Case\\File.txt", "\\\\server\\share\\Case\\File.txt"],
  ["\\\\?\\D:\\Target", "Case\\File.txt", "\\\\?\\D:\\Target\\Case\\File.txt"],
  ["D:\\Target", "", "D:\\Target"],
  [null, "Case\\File.txt", "Case\\File.txt"],
  ["D:\\Target", null, null],
]) assert.equal(formatFilesystemPath(root, path), expected);

let coercions = 0;
const coerciveText = {
  toString() {
    coercions += 1;
    throw new Error("text was coerced");
  },
  [Symbol.toPrimitive]() {
    coercions += 1;
    throw new Error("text was coerced");
  },
};
const target = new TestElement();

assert.throws(
  () => renderText(target, coerciveText),
  /renderText value must be a string/,
);
assert.equal(coercions, 0, "rejected values are not coerced");
assert.equal(setterCalls, 0, "rejected values do not reach textContent");
assert.throws(
  () => renderFilesystemText(target, coerciveText),
  /renderFilesystemText value must be a string/,
);
assert.equal(coercions, 0, "filesystem text rejects before coercion");
assert.equal(
  setterCalls,
  0,
  "rejected filesystem text does not reach textContent",
);

let impostorWrites = 0;
const impostor = {
  set textContent(value) {
    impostorWrites += 1;
    void value;
  },
};
assert.throws(
  () => renderText(impostor, "trusted text"),
  /renderText target must be an Element/,
);
assert.equal(impostorWrites, 0, "non-Elements do not reach a textContent setter");

const unicode = "wave \ud83c\udf0a e\u0301 <img onerror=alert(1)> & 海";
renderText(target, unicode);
assert.equal(target.textContent, unicode);
assert.equal(setterCalls, 1);

const cases = JSON.parse(await readFile(new URL("filesystem_text_cases.json", import.meta.url), "utf8"));
const escapedCodePoints = cases.layout_control_ranges.flatMap(([first, last]) =>
  Array.from({length: last - first + 1}, (_, index) => first + index)
);
escapedCodePoints.push(0x27e6, 0x27e7);

const escapedOutputs = [];
for (const codePoint of escapedCodePoints) {
  renderFilesystemText(target, String.fromCodePoint(codePoint));
  const expected = `⟦U+${codePoint.toString(16).toUpperCase().padStart(4, "0")}⟧`;
  assert.equal(target.textContent, expected, `U+${codePoint.toString(16)}`);
  escapedOutputs.push(target.textContent);
}
assert.equal(
  new Set(escapedOutputs).size,
  escapedCodePoints.length,
  "each escaped code point has a distinct marker",
);

for (const marker of escapedOutputs) {
  renderFilesystemText(target, marker);
  assert.equal(
    target.textContent,
    `⟦U+27E6⟧${marker.slice(1, -1)}⟦U+27E7⟧`,
  );
  assert.notEqual(
    target.textContent,
    marker,
    "literal marker spelling cannot collide with an escaped control",
  );
}

for (const {raw, desktop} of cases.examples) {
  renderFilesystemText(target, raw);
  assert.equal(target.textContent, desktop);
}
renderFilesystemText(target, cases.preserved_text);
assert.equal(target.textContent, cases.preserved_text);

assert.throws(
  () => renderFilesystemText(impostor, "trusted text"),
  /renderText target must be an Element/,
);
assert.equal(impostorWrites, 0, "filesystem text delegates target validation");
