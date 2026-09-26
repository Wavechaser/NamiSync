# Latest session — Recovery feedback and fixed-outcome corrections

2026-09-26, `milestone1`, base `b4b3b72`. The user authorized three validated
follow-up corrections, retaining separate commits without a new checkpoint.
AB-8 remains paused. `67ee229` restores page guidance and fixture ownership;
this following commit simplifies matching invalid-result settlement.

Plan review now selects the retained uncertain execution handle, including after
reconstruction. The renderer repro failed before the fix; the app probe rejects
an execution, checks the same handle after reload, and retains Execute/Close and
selection fences. Page doubles are explicit values and Check spies; sentinel
messages test routing, while actual bridge probes own policy and wording.

Native observation returns the same captured final response, not repaired bytes.
The bridge correction therefore collapses matching invalid results into
noncheckable `fixed-unknown`, with `invalid_result` guidance and exact cleanup ACK.
The earlier probe's in-place response rewrite was not a supported native path.
Communication uncertainty still supports original-result observation. Neither
cleanup nor fixed-unknown claims effect success or permits mutation replay.
Native owners/wire, D4, lifecycle/resource/read bounds and effect fences remain.

Evidence: `build/post-m1-8-ablation-20260925/correction-*`; 7 focused cases and
the final bridge guidance rerun pass. Fresh independent review has no blockers.
All 34 installed tests pass; 12 import contracts are kept. The interfaces gate
had 1781 passes and one stale bridge identity-probe expectation: it treated
fixed-unknown rejection as adoption and expected retries of immutable invalid
data. Corrected that probe to assert uncertain rejection, no adoption/replay and
no observations; its targeted rerun passes (`correction-interactive-consumer2`).
Retain the failed receipt and unaffected passes; no product changes followed them.
Unchanged domain tests retain the predecessor's ordinary-suite evidence; no
domain code changed. Documentation links and diff checks pass.

Use unique external test basetemps and announce each foreground batch before
launch and when finished. Earlier AB-7 Setup `internal_error` and Plan-again
timeouts remain unexplained; this follow-up does not claim their cause or fix.
No new checkout/ref was allocated or deleted. Retain `codex/ab3-mapping` and
AB-6 recovery `56802606` for AB-10; prior AB-7 cleanup remains in
`ab7-cleanup.json`.
