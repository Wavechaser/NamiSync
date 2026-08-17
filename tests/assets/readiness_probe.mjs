import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const listeners = new Map();
const webview = {
  addEventListener(name, callback) {
    listeners.set(name, callback);
  },
  removeEventListener(name, callback) {
    if (listeners.get(name) === callback) listeners.delete(name);
  },
};
const moduleUrl = pathToFileURL(process.argv[2]).href;
const { installReadinessReceiver } = await import(moduleUrl);
const receiver = installReadinessReceiver(webview);
const receive = listeners.get("message");

let firstResolved = false;
const first = receiver.whenReceivedAfter(0).then((challenge) => {
  firstResolved = true;
  return challenge;
});
receive({ data: null });
receive({ data: { kind: "namisync.readiness.v1", challenge: "A".repeat(32) } });
receive({ data: { kind: "namisync.readiness.v1", challenge: "a".repeat(31) } });
receive({
  data: {
    kind: "namisync.readiness.v1",
    challenge: "a".repeat(32),
    unexpected: true,
  },
});
receive({
  data: Object.assign(Object.create(null), {
    kind: "namisync.readiness.v1",
    challenge: "a".repeat(32),
  }),
});
await Promise.resolve();
assert.equal(firstResolved, false);

receive({
  data: { kind: "namisync.readiness.v1", challenge: "a".repeat(32) },
});
assert.equal(await first, "a".repeat(32));
assert.equal(receiver.revision(), 1);

receive({
  data: { kind: "namisync.readiness.v1", challenge: "b".repeat(32) },
});
assert.equal(
  await receiver.whenReceivedAfter(1),
  "b".repeat(32),
  "a challenge received before its waiter must remain buffered",
);
assert.equal(receiver.revision(), 2);
assert.throws(() => receiver.whenReceivedAfter(-1), TypeError);
assert.throws(() => receiver.whenReceivedAfter(3), TypeError);

receiver.close();
assert.equal(listeners.has("message"), false);
process.stdout.write("ok");
