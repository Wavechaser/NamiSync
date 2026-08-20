import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";


class SelectFake {
  constructor(value = "system") {
    this.disabled = false;
    this.value = value;
    this.listeners = new Map();
  }

  addEventListener(name, callback) {
    const callbacks = this.listeners.get(name) ?? [];
    callbacks.push(callback);
    this.listeners.set(name, callbacks);
  }

  removeEventListener(name, callback) {
    const callbacks = this.listeners.get(name) ?? [];
    this.listeners.set(
      name,
      callbacks.filter((candidate) => candidate !== callback),
    );
  }

  choose(value) {
    this.value = value;
    for (const callback of this.listeners.get("change") ?? []) {
      callback();
    }
  }
}

globalThis.HTMLSelectElement = SelectFake;
globalThis.window = {
  addEventListener() {},
};
globalThis.document = {
  documentElement: {
    dataset: { theme: "native-effective-theme" },
  },
};
globalThis.themeHarness = {};

function moduleUrl(source) {
  return `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
}

const bridgeStub = moduleUrl(`
  export class BridgeTransportError extends Error {}
  globalThis.themeHarness.BridgeTransportError = BridgeTransportError;
  export const readCosmeticSection = () => { throw new Error("unexpected default read"); };
  export const replaceCosmeticSection = () => { throw new Error("unexpected default replace"); };
`);
let source = await readFile(process.argv[2], "utf8");
source = source.replace(
  /import \{[\s\S]*?\} from "\.\/bridge\.js";/,
  `import { BridgeTransportError, readCosmeticSection, replaceCosmeticSection } from "${bridgeStub}";`,
);
source = source.replace(
  'import { renderText } from "./render.js";',
  "const renderText = (element, value) => { element.textContent = value; };",
);
const { installThemeSelector } = await import(moduleUrl(source));
const BridgeTransportError = globalThis.themeHarness.BridgeTransportError;

function section(theme, revision) {
  return {
    section: "appearance",
    value_version: 1,
    revision,
    dirty: false,
    value: { theme },
  };
}

function replacement(theme, revision, disposition = "applied") {
  return { ...section(theme, revision), disposition };
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((onResolve, onReject) => {
    resolve = onResolve;
    reject = onReject;
  });
  return { promise, resolve, reject };
}

async function flushUntil(predicate) {
  for (let turn = 0; turn < 48; turn += 1) {
    if (predicate()) {
      return;
    }
    await Promise.resolve();
  }
  assert.fail("theme selector probe did not reach the expected state");
}

async function flushTurns() {
  for (let turn = 0; turn < 12; turn += 1) {
    await Promise.resolve();
  }
}

// Initial cosmetic failure is isolated: the selector stays disabled and an
// unrelated operational readiness label is not replaced.
{
  const select = new SelectFake();
  const shell = { status: "Ready" };
  let reads = 0;
  const controller = installThemeSelector(select, {
    read: async () => {
      reads += 1;
      throw new Error("structured terminal failure");
    },
    replace: async () => assert.fail("replace is unavailable before a read"),
  });
  assert.equal(select.disabled, true);
  assert.equal(reads, 0, "installation does not start the pre-OPEN deadline");
  assert.equal(await controller.refresh(), false);
  assert.equal(reads, 0, "appearance before OPEN cannot start a cosmetic read");
  assert.equal(await controller.open(), false);
  assert.equal(reads, 1);
  assert.equal(select.disabled, true);
  assert.equal(select.value, "system");
  assert.equal(shell.status, "Ready");
}

// A validated native appearance publication refreshes a current selector, so
// a late accepted mutation from an older document cannot leave it stale.
{
  const select = new SelectFake();
  let server = section("system", 0);
  let reads = 0;
  const controller = installThemeSelector(select, {
    read: async () => {
      reads += 1;
      return server;
    },
    replace: async () => assert.fail("no selector replacement is expected"),
  });
  await controller.open();
  server = section("dark", 1);
  assert.equal(await controller.refresh(), true);
  assert.equal(reads, 2);
  assert.equal(select.value, "dark");
  assert.equal(select.disabled, false);
}

// Rapid choices are serialized. The browser restores the last authoritative
// value immediately and uses each accepted revision for the next request.
{
  const select = new SelectFake();
  const attempts = [];
  const first = deferred();
  const second = deferred();
  let active = 0;
  let maximumActive = 0;
  const controller = installThemeSelector(select, {
    read: async () => section("system", 0),
    replace(revision, theme) {
      attempts.push({ revision, theme });
      active += 1;
      maximumActive = Math.max(maximumActive, active);
      const pending = attempts.length === 1 ? first : second;
      return pending.promise.finally(() => {
        active -= 1;
      });
    },
  });
  assert.equal(await controller.open(), true);
  assert.equal(select.disabled, false);

  select.choose("light");
  assert.equal(select.disabled, true);
  assert.equal(select.value, "system", "the choice is not rendered optimistically");
  await flushUntil(() => attempts.length === 1);
  select.choose("dark");
  assert.equal(select.value, "system");
  assert.equal(attempts.length, 1);

  first.resolve(replacement("light", 1));
  await flushUntil(() => attempts.length === 2);
  assert.deepEqual(attempts, [
    { revision: 0, theme: "light" },
    { revision: 1, theme: "dark" },
  ]);
  assert.equal(select.value, "light");
  second.resolve(replacement("dark", 2));
  await flushUntil(() => !select.disabled);
  assert.equal(select.value, "dark");
  assert.equal(maximumActive, 1);
}

// A conflict result is authoritative and settles without replaying the user's
// stale intent.
{
  const select = new SelectFake();
  const attempts = [];
  const controller = installThemeSelector(select, {
    read: async () => section("light", 4),
    replace: async (revision, theme) => {
      attempts.push({ revision, theme });
      return replacement("system", 5, "conflict");
    },
  });
  await controller.open();
  select.choose("dark");
  await flushUntil(() => !select.disabled);
  assert.deepEqual(attempts, [{ revision: 4, theme: "dark" }]);
  assert.equal(select.value, "system");
}

// An uncertain but accepted replacement is reconciled by a guarded read. The
// mutating request itself is never replayed.
{
  const select = new SelectFake();
  let reads = 0;
  let replacements = 0;
  const controller = installThemeSelector(select, {
    read: async () => {
      reads += 1;
      return reads === 1 ? section("system", 0) : section("dark", 1);
    },
    replace: async () => {
      replacements += 1;
      throw new BridgeTransportError("uncertain replacement");
    },
  });
  await controller.open();
  select.choose("dark");
  await flushUntil(() => !select.disabled);
  assert.equal(reads, 2);
  assert.equal(replacements, 1);
  assert.equal(select.value, "dark");
}

// A stale result cannot regress the accepted revision or value.
{
  const select = new SelectFake();
  const controller = installThemeSelector(select, {
    read: async () => section("dark", 8),
    replace: async () => replacement("light", 7),
  });
  await controller.open();
  select.choose("light");
  await flushTurns();
  assert.equal(select.value, "dark");
  assert.equal(select.disabled, true);
}

// A terminal replacement failure preserves the confirmed value and disables
// the isolated control without producing another request or shell warning.
{
  const select = new SelectFake();
  let replacements = 0;
  const shell = { status: "Ready" };
  const controller = installThemeSelector(select, {
    read: async () => section("light", 3),
    replace: async () => {
      replacements += 1;
      throw new Error("terminal command refusal");
    },
  });
  await controller.open();
  select.choose("dark");
  await flushTurns();
  assert.equal(replacements, 1);
  assert.equal(select.value, "light");
  assert.equal(select.disabled, true);
  assert.equal(shell.status, "Ready");
}

// A DOM value outside the fixed schema cannot reach the bridge and cannot
// displace the last confirmed selection.
{
  const select = new SelectFake();
  let replacements = 0;
  const controller = installThemeSelector(select, {
    read: async () => section("system", 1),
    replace: async () => {
      replacements += 1;
      return replacement("system", 1, "noop");
    },
  });
  await controller.open();
  select.choose("sepia");
  assert.equal(replacements, 0);
  assert.equal(select.value, "system");
  assert.equal(select.disabled, true);
}

// If uncertainty cannot be reconciled, the last confirmed value remains and
// the control cannot admit another mutation.
{
  const select = new SelectFake();
  let reads = 0;
  const controller = installThemeSelector(select, {
    read: async () => {
      reads += 1;
      if (reads === 1) return section("light", 2);
      throw new BridgeTransportError("uncertain reconciliation");
    },
    replace: async () => {
      throw new BridgeTransportError("uncertain replacement");
    },
  });
  await controller.open();
  select.choose("dark");
  await flushTurns();
  assert.equal(reads, 2);
  assert.equal(select.value, "light");
  assert.equal(select.disabled, true);
}

// An unchanged revision after uncertain delivery is not proof that the
// admitted replacement cannot still land. The selector stays disabled.
{
  const select = new SelectFake();
  let reads = 0;
  const controller = installThemeSelector(select, {
    read: async () => {
      reads += 1;
      return section("light", 2);
    },
    replace: async () => {
      throw new BridgeTransportError("uncertain replacement");
    },
  });
  await controller.open();
  select.choose("dark");
  await flushTurns();
  assert.equal(reads, 2);
  assert.equal(select.value, "light");
  assert.equal(select.disabled, true);
}

// A new bridge generation waits for an admitted old replacement to settle
// before it reads and enables its own authoritative state.
{
  const select = new SelectFake();
  const admitted = deferred();
  let reads = 0;
  const controller = installThemeSelector(select, {
    read: async () => {
      reads += 1;
      return reads === 1 ? section("system", 0) : section("dark", 1);
    },
    replace: () => admitted.promise,
  });
  await controller.open();
  select.choose("dark");
  await flushUntil(() => select.disabled);
  controller.invalidate();
  const reopened = controller.open();
  await flushTurns();
  assert.equal(reads, 1, "the new generation cannot overtake the old mutation");
  admitted.resolve(replacement("dark", 1));
  assert.equal(await reopened, true);
  assert.equal(reads, 2);
  assert.equal(select.value, "dark");
  assert.equal(select.disabled, false);
}

// A later bridge generation owns the selector even when an older read settles
// afterward.
{
  const select = new SelectFake();
  const stale = deferred();
  let reads = 0;
  const controller = installThemeSelector(select, {
    read() {
      reads += 1;
      return reads === 1 ? stale.promise : Promise.resolve(section("light", 2));
    },
    replace: async () => assert.fail("no replacement is expected"),
  });
  const oldOpen = controller.open();
  controller.invalidate();
  assert.equal(select.disabled, true);
  assert.equal(await controller.open(), true);
  assert.equal(select.value, "light");
  stale.resolve(section("dark", 99));
  assert.equal(await oldOpen, false);
  assert.equal(select.value, "light");
  assert.equal(select.disabled, false);
}

assert.equal(
  document.documentElement.dataset.theme,
  "native-effective-theme",
  "the selector never competes with the native appearance envelope",
);
process.stdout.write("ok");
