import { pathToFileURL } from "node:url";

class HTMLElementFake {
  constructor() {
    this.dataset = {};
    this.properties = new Map();
    this.style = {
      setProperty: (name, value) => this.properties.set(name, value),
    };
  }
}

globalThis.HTMLElement = HTMLElementFake;

const listeners = new Map();
const webview = {
  addEventListener(name, callback) {
    listeners.set(name, callback);
  },
  removeEventListener(name, callback) {
    if (listeners.get(name) === callback) listeners.delete(name);
  },
};
const root = new HTMLElementFake();
const moduleUrl = pathToFileURL(process.argv[2]).href;
const { installAppearanceReceiver } = await import(moduleUrl);
let observerCalls = 0;
const receiver = installAppearanceReceiver(webview, root, () => {
  observerCalls += 1;
});
const receive = listeners.get("message");
let applied = false;
const firstApplication = receiver.whenApplied().then(() => {
  applied = true;
});
const base = {
  kind: "namisync.appearance.v2",
  revision: 2,
  theme: "dark",
  highContrast: false,
  material: "mica",
  accentFill: "#123456",
  accentFillHover: "#123456E6",
  accentFillPressed: "#123456CC",
  accentFillForeground: "#FFFFFF",
};

receive({ data: { ...base, revision: 1, accentFill: "red;url(x)" } });
await Promise.resolve();
const resolvedBeforeValidMessage = applied;
receive({ data: base });
await firstApplication;
const resolvedAfterValidMessage = applied;
let reapplied = false;
const nextApplication = receiver.whenAppliedAfter(2).then(() => {
  reapplied = true;
});
receive({ data: { ...base, revision: 1, accentFill: "#999999" } });
receive({ data: { ...base, revision: 3, accentFill: "red;url(x)" } });
receive({ data: { ...base, revision: 4, accentFillHover: "#123456" } });
receive({ data: { ...base, revision: 5, unexpected: true } });
receive({ data: Object.assign(Object.create(null), { ...base, revision: 6 }) });
await Promise.resolve();
const resolvedBeforeNewRevision = reapplied;
receive({ data: { ...base, revision: 7, material: "degraded", theme: "light" } });
await nextApplication;

const result = {
  revision: receiver.revision(),
  dataset: root.dataset,
  properties: Object.fromEntries(root.properties),
  resolvedBeforeValidMessage,
  resolvedAfterValidMessage,
  resolvedBeforeNewRevision,
  resolvedAfterNewRevision: reapplied,
  observerCalls,
};
receiver.close();
result.listenerRemoved = !listeners.has("message");
process.stdout.write(JSON.stringify(result));
