import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";


function moduleUrl(source) {
  return `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
}


globalThis.window = { chrome: { webview: {} } };
let installCount = 0;
let revision = 0;
let latestChallenge;
let waiters = [];
let activePlan;
let shellCalls = 0;
let operationalMarks = 0;
const echoCalls = [];

function emitChallenge(challenge) {
  revision += 1;
  latestChallenge = challenge;
  const ready = waiters.filter((waiter) => revision > waiter.baseline);
  waiters = waiters.filter((waiter) => revision <= waiter.baseline);
  for (const waiter of ready) waiter.resolve(challenge);
}

const readiness = Object.freeze({
  revision: () => revision,
  whenReceivedAfter(baseline) {
    if (revision > baseline) return Promise.resolve(latestChallenge);
    return new Promise((resolve) => waiters.push({ baseline, resolve }));
  },
});

globalThis.bootstrapHarness = {
  installReadiness() {
    installCount += 1;
    return readiness;
  },
  async acknowledgeShell() {
    shellCalls += 1;
    if (activePlan.deferChallenge) {
      setTimeout(() => emitChallenge(activePlan.challenge), 0);
    } else {
      emitChallenge(activePlan.challenge);
    }
    if (activePlan.shellError !== undefined) throw activePlan.shellError;
    return { acknowledged: true };
  },
  async echo(challenge) {
    echoCalls.push(challenge);
    const outcome = activePlan.echoes.shift();
    if (outcome instanceof Error) throw outcome;
    return { acknowledged: outcome };
  },
  markOperational() {
    operationalMarks += 1;
  },
};

const bridgeStub = moduleUrl(`
  export class BridgeTransportError extends Error {}
  globalThis.bootstrapHarness.BridgeTransportError = BridgeTransportError;
  export const whenBridgeApiReady = () => Promise.resolve();
  export const acknowledgeShellReady = () => globalThis.bootstrapHarness.acknowledgeShell();
  export const echoReadiness = (challenge) => globalThis.bootstrapHarness.echo(challenge);
  export const markBridgeOperational = () => globalThis.bootstrapHarness.markOperational();
`);
const readinessStub = moduleUrl(`
  export const installReadinessReceiver = () => globalThis.bootstrapHarness.installReadiness();
`);
let source = await readFile(process.argv[2], "utf8");
source = source
  .replace("./bridge.js", bridgeStub)
  .replace("./readiness.js", readinessStub);
const {
  bootstrapTestBridge,
  installTestBridgeReadiness,
} = await import(moduleUrl(source));
const BridgeTransportError = globalThis.bootstrapHarness.BridgeTransportError;

assert.equal(installTestBridgeReadiness(), readiness);
assert.equal(installTestBridgeReadiness(), readiness);
assert.equal(installCount, 1);

activePlan = {
  challenge: "a".repeat(32),
  shellError: new BridgeTransportError(),
  echoes: [false, true],
};
await bootstrapTestBridge();
assert.deepEqual(echoCalls.splice(0), ["a".repeat(32), "a".repeat(32)]);
assert.equal(operationalMarks, 1);

emitChallenge("9".repeat(32));
activePlan = {
  challenge: "b".repeat(32),
  deferChallenge: true,
  echoes: [new BridgeTransportError(), true],
};
await bootstrapTestBridge();
assert.deepEqual(echoCalls.splice(0), ["b".repeat(32), "b".repeat(32)]);
assert.equal(revision, 3);
assert.equal(installCount, 1);
assert.equal(operationalMarks, 2);

const nonTransportEcho = new Error("non-transport echo failure");
activePlan = {
  challenge: "c".repeat(32),
  echoes: [nonTransportEcho, true],
};
await assert.rejects(bootstrapTestBridge(), (error) => error === nonTransportEcho);
assert.deepEqual(echoCalls.splice(0), ["c".repeat(32)]);
assert.equal(operationalMarks, 2);

const nonTransportShell = new Error("non-transport shell failure");
activePlan = {
  challenge: "d".repeat(32),
  shellError: nonTransportShell,
  echoes: [true],
};
await assert.rejects(bootstrapTestBridge(), (error) => error === nonTransportShell);
assert.deepEqual(echoCalls.splice(0), []);
assert.equal(operationalMarks, 2);

activePlan = {
  challenge: "e".repeat(32),
  echoes: [false, false, true],
};
await assert.rejects(bootstrapTestBridge(), BridgeTransportError);
assert.deepEqual(echoCalls.splice(0), ["e".repeat(32), "e".repeat(32)]);
assert.equal(operationalMarks, 2);

const rawCalls = [];
let rawEchoes = 0;
activePlan = { challenge: "f".repeat(32), echoes: [] };
await bootstrapTestBridge({
  async dispatchCommand(command, payload) {
    rawCalls.push([command, payload]);
    if (command === "shell_ready") {
      emitChallenge(activePlan.challenge);
      return { ok: true, result: { acknowledged: true } };
    }
    rawEchoes += 1;
    if (rawEchoes === 1) throw new Error("raw return uncertainty");
    return { ok: true, result: { acknowledged: true } };
  },
});
assert.deepEqual(rawCalls, [
  ["shell_ready", {}],
  ["readiness_echo", { challenge: "f".repeat(32) }],
  ["readiness_echo", { challenge: "f".repeat(32) }],
]);
assert.equal(shellCalls, 5);
assert.equal(installCount, 1);
assert.equal(operationalMarks, 3);
process.stdout.write("ok");
