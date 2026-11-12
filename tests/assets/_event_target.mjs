// Tests-only listener mechanics shared by the four bridge probes.
export class TestEventTarget {
  constructor() {
    this.listeners = new Map();
  }

  addEventListener(name, handler, options = {}) {
    const listeners = this.listeners.get(name) ?? [];
    listeners.push({ handler, once: options.once === true });
    this.listeners.set(name, listeners);
  }

  removeEventListener(name, handler) {
    const listeners = this.listeners.get(name) ?? [];
    this.listeners.set(
      name,
      listeners.filter((listener) => listener.handler !== handler),
    );
  }

  emit(name) {
    for (const listener of [...(this.listeners.get(name) ?? [])]) {
      if (listener.once) {
        this.removeEventListener(name, listener.handler);
      }
      listener.handler();
    }
  }

  listenerCount(name) {
    return (this.listeners.get(name) ?? []).length;
  }
}
