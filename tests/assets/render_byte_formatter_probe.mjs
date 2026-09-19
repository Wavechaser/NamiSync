import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const source = await readFile(process.argv[2], "utf8");
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const { formatByteCount } = await import(moduleUrl);

const cases = new Map([
  ["0", "0 B"],
  ["999", "999 B"],
  ["1023", "1023 B"],
  ["1024", "1.00 KiB"],
  ["1536", "1.50 KiB"],
  ["1048575", "1.00 MiB"],
  ["1048570", "1023.99 KiB"],
  [String(12n * 1024n ** 2n), "12.00 MiB"],
  [String(120n * 1024n ** 2n), "120.00 MiB"],
  [String(10n * 1024n ** 2n + 512n * 1024n), "10.50 MiB"],
  ["10485236", "10.00 MiB"],
  [String(1023n * 1024n + 512n), "1023.50 KiB"],
  ["9007200168568816", "8.00 PiB"],
  [String(2n ** 60n), "1.00 EiB"],
  [String(2n ** 63n - 1n), "8.00 EiB"],
]);
for (const [value, expected] of cases) assert.equal(formatByteCount(value), expected, value);
assert.equal(formatByteCount(1000), "1000 B");
assert.equal(formatByteCount(1536), "1.50 KiB");
assert.equal(formatByteCount(1536n), "1.50 KiB");
assert.throws(() => formatByteCount(-1), /non-negative/);
assert.throws(() => formatByteCount("1.5"), /decimal integer/);
assert.throws(() => formatByteCount(Number.MAX_SAFE_INTEGER + 1), /safe integer/);
