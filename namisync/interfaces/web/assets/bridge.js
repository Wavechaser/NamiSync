let readiness;

export function whenBridgeReady() {
  if (window.pywebview?.api?.dispatch) {
    return Promise.resolve();
  }
  if (!readiness) {
    readiness = new Promise((resolve) => {
      window.addEventListener("pywebviewready", resolve, { once: true });
    });
  }
  return readiness;
}
