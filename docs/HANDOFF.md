# Session Handoff

Status (2026-09-03): LC-4 is complete on `milestone1-anthony`. Production still
uses the dispatcher parallel maps; only the probe observation is pending this
commit. LC-5 is the next register row.

## LC-4 outcome

- The current finite denominator is seven entry-local session containers, not
  the historical nine. Scheduler/custody/current-worker/admission-cleanup state
  remains a separate global concern.
- On disposable branch `codex/session-entry-feasibility`, a frozen, slotted,
  behaviorless `_SessionEntry` consolidated those seven containers. The exact
  four declared mutators owned every aggregate-map write.
- A finite AST gate covered ordinary assignment/deletion/mapping mutation,
  aliases, and entry-field writes. A test-only mapping checked
  `Condition._is_owned()` at each actual write and rejected a deliberate
  unlocked mutation. This is exercised-path evidence, not universal lock proof.
- The aggregate is shallow: `_Control`, `EventHub`, `Lock`, and the item list
  retain their own mutation/synchronization. The prototype rewrote 78 reads and
  27 mutations, added 101 net dispatcher lines, and initially retained a closed
  checkpoint in a scheduler-frame aggregate local. The corrected scratch path
  passed, but the incident demonstrates complexity and retention-risk movement.
- Accepted result: keep the parallel maps. All four scratch paths were restored,
  final diff/search evidence was empty, and the disposable branch was deleted.

## Verification

- Structural/write-time scratch probes: `2 passed`, including unlocked fault.
- Named concurrency/custody slice: `7 passed`.
- Dispatcher department after temporary private-test reanchoring:
  `157 passed, 4820 deselected`.
- Independent adversarial review: no basis for a stronger lock-safety claim.
- Final production/test scratch search and diff: empty.

## Next action

Run LC-5 on a new disposable branch from this observation commit. The exact
twelve-file domain in `docs/TASK_LIFECYCLE_SIMPLIFICATION.md` is the complete
scope gate. Exercise a non-null `OperationResult.simplification_probe` through
snapshot, terminal events, stored/live records, public views, CLI, Python
bridge serialization, and real JavaScript validation; prove default-null bytes
remain unchanged; record the raw path list; then reverse all probe code.

The historical `.codex` plan remains untouched. Old recovery/WIP refs remain
isolated and are not review units.
