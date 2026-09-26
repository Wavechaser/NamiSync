// Small page-fixture value; production bridge.js owns recovery behavior.
export function fakeRecoveryHandle(check = null, state = "unavailable") {
  let checkPromise = null;
  return {
    state,
    checking: false,
    configure(nextCheck, nextState = "unavailable") {
      check = nextCheck;
      this.state = nextState;
    },
    get canCheck() {
      return typeof check === "function"
        && ["pending", "unavailable", "protocol-fault"].includes(this.state);
    },
    get message() {
      if (this.state === "settled") return null;
      if (this.state === "fixed-unknown") {
        return "Original outcome cannot be confirmed. Close and reopen NamiSync to review current state.";
      }
      if (this.checking) return "Checking the original outcome…";
      return this.state === "submitting" ? null
        : "Outcome unavailable. Select Check outcome to observe the original request, or close and reopen NamiSync to review current state.";
    },
    check() {
      if (checkPromise !== null) return checkPromise;
      this.checking = true;
      checkPromise = Promise.resolve().then(() => check?.()).finally(() => {
        this.checking = false;
        checkPromise = null;
      });
      return checkPromise;
    },
  };
}
