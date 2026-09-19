# Latest session handoff

## M1-8-capacity delivered; execution review next (2026-09-20)

Authorized batch: M1-8-capacity and M1-8, then stop for recap and GUI tweaks.
Original baseline `2cc0083` on `milestone1` was clean. Preparation/GUI record
condensation committed as `42ff8f2`; capacity is the following reviewed
`feat(executor): stop on recognized capacity failure` commit. No push, PR,
DOC-2, M1-9 or release authorization.

Capacity recognizes native 39/112/1295 and ENOSPC without native codes, follows
explicit/executor-semantic causes and preserves stronger typed reasons. The
existing Stop sweep leaves later work unrun after current settlement. A8-02
covers capacity introduced by MKDIR start and both cleanup paths. Recorder-only
writes remain recording degradation/continuation; prerequisites can stop.
Deferred directory finalization and exit/recording settlement remain unchanged.

Verification:

- Consumer neighborhood: 3,968 passed, two skipped.
- Ordinary: 5,216 passed, five skipped, 31 headed deselected.
- Skips: four unavailable symlink privileges; optional M1-7 readiness artifact
  not configured. No required capacity witness skipped.
- Latest test-only post-publication/recorder-only/MKDIR-sharing controls passed;
  independent final focused review passed 17 cases.
- Unchanged settlement oracle: 30 scenarios x 3 runs.
- All 12 import contracts, 86 local documentation links, diff checks and fresh
  adversarial review passed. No tests/oracle baselines retired.

Final logs: `build/m1-8-capacity-neighborhood-final01.log`,
`build/m1-8-capacity-ordinary-final01.log`,
`build/m1-8-capacity-oracle-final.log`. Earlier logs retain failed default-temp
permission and source-tree custody-fixture attempts; they are not passes.
Final broad tests used fresh external native temp fixtures; no harness softened.

Next: M1-8-E bounded atomic ledger evidence, then P1 retained backend review,
P2 bounded protocol, U GUI. M1_PLAN owns finite rows and E expansion. The
read-only E builder awaits integrated-capacity authorization. No E product code
has started. Root owns M1_PLAN/CHANGELOG/HANDOFF; builders own named component
code/tests/docs. No task-created worktree or branch yet; artifacts stay ignored.

Arbiter task `01a0ba9c-b187-70f1-bf21-4f91e742eeaf` is authoritative for stops.
A8-01 approves exact task-owned result retention before terminal release,
idempotent partial-cleanup retry, separate linked overlay, visible Gap history,
and close/shutdown retirement. A8-02 approves the finite capacity bypass remedy;
its table and exclusions are in M1_PLAN. New boundaries return to that arbiter.

Historical GUI-M2 recovery `af02913` and stash `93414b7` remain preserved, not
merge units; useful changes were rebuilt in `7cf4448`. Earlier GUI evidence is
in the condensed register, CHANGELOG and historical HANDOFF snapshots.
