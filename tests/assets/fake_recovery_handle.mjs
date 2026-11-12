// Page probes supply recovery facts; production bridge.js owns recovery behavior.
export function fakeRecoveryHandle({
  state = "unavailable", canCheck = false, checking = false,
  message = "fixture-recovery-status", check = () => Promise.resolve(null),
} = {}) {
  return { state, canCheck, checking, message, check };
}
