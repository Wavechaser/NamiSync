import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const source = await readFile(process.argv[2], "utf8");
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const { formatByteCount } = await import(moduleUrl);

const cases = new Map([
  ["0", "0 B"],
  ["1023", "1023 B"],
  ["1024", "1 KiB"],
  ["1536", "1.5 KiB"],
  [String(10n * 1024n ** 2n + 512n * 1024n), "10.5 MiB"],
  ["9007200168568816", "8 PiB"],
  [String(2n ** 60n), "1 EiB"],
]);
for (const [value, expected] of cases) assert.equal(formatByteCount(value), expected, value);
assert.equal(formatByteCount(1536), "1.5 KiB");
assert.equal(formatByteCount(1536n), "1.5 KiB");
assert.throws(() => formatByteCount(-1), /non-negative/);
assert.throws(() => formatByteCount("1.5"), /decimal integer/);
assert.throws(() => formatByteCount(Number.MAX_SAFE_INTEGER + 1), /safe integer/);
