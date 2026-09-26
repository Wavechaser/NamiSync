# Latest session — AB-8 follow-up delivered; recap pause

2026-09-26. The six user-reported AB-8 findings were validated and corrected on
`milestone1`, based on `7445f70a`, as `fix(web): contain task presentation faults`.
**Do not implement AB-9/10 without new authorization.** M1_PLAN retains AB-8's
acceptance contract, regression watchlist and adversarial check for the final sweep.

Matching snapshots now exclusively supply page terminal state/result/timestamps
through one selector; retained execution results are a fallback without a matching
snapshot. Same-session captured window counts/trash remain available for capacity
guidance. Redundant page copies, revision filtering and unused snapshot wire fields
are removed. Internal snapshot wire version is 2; full event bodies remain.

The sink timestamps accepted/coalesced Progress independently of its linger
deadline, preserving the sample through partial or failed delivery. Named semantic
progress conflicts now clear uncertain presentation, retain a visible diagnostic
and log one bounded internal error on committed degradation. Terminal delivery
continues; malformed values, identity/byte walls and terminal contradictions remain
strict. Historical-source witnesses confirm both defects. The user's exact rate
table was not an installed-path measurement: production coalesces queued Progress.

Verification: **5,369 passed, 4 Windows symlink-privilege skips**, including installed
journeys; **12 import contracts kept**; fresh independent review found no blocker;
documentation links/diff checked. Focused native/page/integration passes and failed
receipts remain in `build/ab8-followup-20260926/`. Its `validation.md` records the
finding dispositions; 51 installed receipts/captures were preserved. The baseline
overflow test's first-batch count was a scheduling assumption; its exact recovery,
retained tail, missing-item and terminal assertions remain. Product net +12 lines;
tests net +197 lines. No fresh Claude review was requested for this follow-up;
the prior AB-8 Opus 5.5/high review remains in `build/ab8-resume-20260926/`.

No task recovery branch or disposable checkout was created this session. Prior
AB-8 recovery is accounted for in `build/ab8-resume-20260926/integration.json` and
its verified `recovery.bundle`. Preserve unrelated `codex/ab3-mapping` and AB-6
recovery `56802606` for AB-10 accounting. Earlier unexplained AB-7 observations and
the original AB-8 stack/wrap rerun remain unexplained; this work does not close them.

For native tests use a unique basetemp, `PIP_NO_CACHE_DIR=1`, native desktop access
and process-only `PSExecutionPolicyPreference=RemoteSigned`. Announce every
foreground batch and when the desktop is free. The desktop is free at handoff;
the completed test process has exited. Raw test fixtures remain in the unique
temporary directory; no user files were touched or unrelated processes stopped.
