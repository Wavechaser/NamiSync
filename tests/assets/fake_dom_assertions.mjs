import assert from "node:assert/strict";

export function assertSameNode(actual, expected, message) {
  if (actual !== expected) assert.fail(message ?? "fake DOM node identity changed");
}

export function assertSameNodes(actual, expected, message) {
  assert.equal(actual.length, expected.length, message);
  for (let index = 0; index < actual.length; index += 1) {
    assertSameNode(actual[index], expected[index], `${message} at index ${index}`);
  }
}
