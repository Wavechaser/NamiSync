# Latest session handoff

## M1-8 evidence read delivered; retention next (2026-09-20)

Authorized batch: M1-8-capacity and M1-8, then stop for recap and GUI tweaks.
Original clean baseline `2cc0083` on `milestone1`; preparation/GUI condensation
`42ff8f2`, reviewed capacity `04947ba`. No push, PR, DOC-2, M1-9 or release.

M1-8-E implements an exact <=256-subject current-ledger read in one SQLite
snapshot (at most three data SELECTs), with workflow-owned five-state evidence
classification and runtime/service forwarding. Empty reads open no reader;
closed runtime still refuses. Successful zero-byte copy-like items are eligible.
Missing/mismatched receipt is unrecorded; incoherent/ambiguous current evidence
is superseded. Only coherent copy/verified states expose existing xxh3_128
content. Recording degradation stays independent. No schema, recorder, history,
Plan hierarchy, dispatcher, web protocol or GUI changes belong to E.

E verification: final focused module nine passed; initial direct files
247 passed; consumer neighborhood 2,960 passed, one optional M1-7 readiness
artifact skip. Final ordinary: 5,226 passed, five unchanged skips (four symlink
privileges and the optional artifact), 31 headed deselections. Raw evidence:
`build/m1-8-e-ordinary-final01.log`. Neighborhood raw result is
`build/m1-8-e-neighborhood-02.log`; the first attempt used an invalid department
name and collected nothing. Final source guard/closed-empty corrections are
covered by focused tests and the final ordinary run. Twelve import contracts,
59 local documentation links and diff checks passed. Fresh final adversarial
review passed. E is the following `feat(workflows): classify bounded execution
evidence` commit after `04947ba`. No protected artifact or test was retired.

Next is M1-8-P1, whose finite boundary and A8-01 authority are in M1_PLAN.
Terminal dispatcher checkpoints are always absent: capture exact core result
before custody release, using the service's retained committed Plan/selection
and exact task/session/run association. Item-free delivery cannot reconstruct
it. Preserve review through partial cleanup/retry; dispose at successful Close
and completed shutdown. Derive target ownership once from all selected target
and move-prior touches, including failed/missing selected competitors.
P2 adds compact windows and separate detail under existing byte limits; U adds
GUI. Full reliable items may reach 1 MiB, so no 256-item full-detail wire dump.

Root owns M1_PLAN/CHANGELOG/HANDOFF. The retention builder is read-only until E
is reviewed/committed. No task-created worktree or branch; temporary evidence
stays in ignored build. Use native external TEMP basetemp/cache for broad tests;
source-tree temp invalidates protected custody fixtures. Capacity final gates:
5,216 ordinary tests; 3,968 neighborhood; unchanged 30-scenario x3 oracle, imports
and independent review. Logs remain `build/m1-8-capacity-*-final01.log` and
`build/m1-8-capacity-oracle-final.log`.

Arbiter task `01a0ba9c-b187-70f1-bf21-4f91e742eeaf` is authoritative for stops.
A8-01 owns lifetime extension; A8-02's finite capacity bypass remedy is delivered.
New boundaries return to that arbiter. Historical GUI recovery `af02913` and
stash `93414b7` remain preserved, not merge units; useful changes are in `7cf4448`.
