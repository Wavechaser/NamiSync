const MESSAGE_KIND = "namisync.readiness.v1";
const CHALLENGE = /^[0-9a-f]{32}$/;
const KEYS = Object.freeze(["challenge", "kind"]);

function isReadinessMessage(value) {
  if (
    value === null
    || typeof value !== "object"
    || Array.isArray(value)
    || Object.getPrototypeOf(value) !== Object.prototype
  ) {
    return false;
  }
  const keys = Object.keys(value).sort();
  return keys.length === KEYS.length
    && keys.every((key, index) => key === KEYS[index])
    && value.kind === MESSAGE_KIND
    && typeof value.challenge === "string"
    && CHALLENGE.test(value.challenge);
}

export function installReadinessReceiver(webview) {
  if (
    webview === null
    || typeof webview !== "object"
    || typeof webview.addEventListener !== "function"
    || typeof webview.removeEventListener !== "function"
  ) {
    throw new TypeError("WebView2 readiness receiver is unavailable");
  }

  let revision = 0;
  let latestChallenge = null;
  let challengeWaiters = [];
  const receive = (event) => {
    const value = event?.data;
    if (!isReadinessMessage(value)) {
      return;
    }
    revision += 1;
    latestChallenge = value.challenge;
    const ready = challengeWaiters.filter(
      (waiter) => revision > waiter.previousRevision,
    );
    challengeWaiters = challengeWaiters.filter(
      (waiter) => revision <= waiter.previousRevision,
    );
    for (const waiter of ready) waiter.resolve(latestChallenge);
  };

  const whenReceivedAfter = (previousRevision) => {
    if (
      !Number.isSafeInteger(previousRevision)
      || previousRevision < 0
      || previousRevision > revision
    ) {
      throw new TypeError("Readiness baseline revision is invalid");
    }
    if (revision > previousRevision) {
      return Promise.resolve(latestChallenge);
    }
    const existing = challengeWaiters.find(
      (waiter) => waiter.previousRevision === previousRevision,
    );
    if (existing !== undefined) {
      return existing.promise;
    }
    let resolveChallenge;
    const promise = new Promise((resolve) => {
      resolveChallenge = resolve;
    });
    challengeWaiters.push({
      previousRevision,
      promise,
      resolve: resolveChallenge,
    });
    return promise;
  };

  webview.addEventListener("message", receive);
  return Object.freeze({
    close() {
      webview.removeEventListener("message", receive);
    },
    revision() {
      return revision;
    },
    whenReceivedAfter,
  });
}
