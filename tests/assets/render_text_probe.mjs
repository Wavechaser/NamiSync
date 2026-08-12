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
const { renderText } = await import(moduleUrl);

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
