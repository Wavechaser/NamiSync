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
const receiver = installAppearanceReceiver(webview, root);
const receive = listeners.get("message");
const base = {
  kind: "namisync.appearance.v1",
  revision: 2,
  theme: "dark",
  highContrast: false,
  material: "mica",
  accent: "#123456",
  accentHover: "#234567",
  accentPressed: "#012345",
  accentForeground: "#FFFFFF",
  accentHoverForeground: "#FFFFFF",
  accentPressedForeground: "#FFFFFF",
};

receive({ data: base });
receive({ data: { ...base, revision: 1, accent: "#999999" } });
receive({ data: { ...base, revision: 3, accent: "red;url(x)" } });
receive({ data: { ...base, revision: 4, unexpected: true } });
receive({ data: Object.assign(Object.create(null), { ...base, revision: 5 }) });

const result = {
  revision: receiver.revision(),
  dataset: root.dataset,
  properties: Object.fromEntries(root.properties),
};
receiver.close();
result.listenerRemoved = !listeners.has("message");
process.stdout.write(JSON.stringify(result));
