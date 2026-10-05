import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const source = await readFile(process.argv[2], "utf8");
const { formatLocalDateTime } = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);

process.env.TZ = "UTC";
assert.equal(formatLocalDateTime("2026-10-05T23:04:59.999999+00:00"), "2026-10-05 23:04");
assert.equal(formatLocalDateTime(0), "1970-01-01 00:00");
assert.equal(formatLocalDateTime(Number(9223372036854775807n / 1000000n)), "2262-04-11 23:47");
assert.equal(formatLocalDateTime("0001-01-01T00:00:00+00:00"), "0001-01-01 00:00");
for (const value of [null, undefined, "invalid", "", NaN, Infinity]) {
  assert.equal(formatLocalDateTime(value), null);
}
process.env.TZ = "Asia/Shanghai";
assert.equal(formatLocalDateTime("2026-12-31T23:04:59+00:00"), "2027-01-01 07:04");
assert.equal(formatLocalDateTime(0), "1970-01-01 08:00");
process.env.TZ = "America/New_York";
assert.equal(formatLocalDateTime("2026-01-01T00:04:59+00:00"), "2025-12-31 19:04");
