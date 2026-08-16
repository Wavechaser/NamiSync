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
const { renderFilesystemText, renderText } = await import(moduleUrl);

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

const escapedCodePoints = [];
for (let codePoint = 0x0000; codePoint <= 0x001f; codePoint += 1) {
  escapedCodePoints.push(codePoint);
}
for (let codePoint = 0x007f; codePoint <= 0x009f; codePoint += 1) {
  escapedCodePoints.push(codePoint);
}
escapedCodePoints.push(0x00ad, 0x061c, 0x200b, 0x200e, 0x200f);
for (let codePoint = 0x2028; codePoint <= 0x202e; codePoint += 1) {
  escapedCodePoints.push(codePoint);
}
for (let codePoint = 0x2060; codePoint <= 0x206f; codePoint += 1) {
  escapedCodePoints.push(codePoint);
}
escapedCodePoints.push(0xfeff, 0x27e6, 0x27e7);

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

const preserved =
  "<img onerror=alert(1)> العربية עברית e\u0301 🌊\ufe0f A\u200cB\u200dC \u{e0020}";
renderFilesystemText(target, preserved);
assert.equal(target.textContent, preserved);

assert.throws(
  () => renderFilesystemText(impostor, "trusted text"),
  /renderText target must be an Element/,
);
assert.equal(impostorWrites, 0, "filesystem text delegates target validation");
