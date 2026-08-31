# Session Handoff

Status (2026-09-01): the ratified initial simplification run is complete through
SIM-1 on `milestone1-anthony`. Process-local workflow payload serialization has
been removed and replaced by detached typed checkpoint custody. SIM-2 is the
only active row. H2 checkpoints 5-8 and every new feature remain out of scope.

## Delivered

- Deleted `namisync/workflows/payloads.py`,
  `namisync/workflows/_json_envelope.py`, and the inventory/integrity codec and
  charge closure. All eight internal codec entry points and 134 codec/JSON
  helper functions are gone.
- Dispatcher/session custody now carries one opaque object and never inspects
  its semantics. Frozen plan, inventory, and integrity requests serve directly
  as checkpoints. Execution adds one `ExecutionCheckpoint` using the existing
  execution/selection snapshots and returns fresh mutable state from one
  `materialize()` path; there is no checkpoint authority, adoption, schema,
  version, generic freezer, or compatibility representation.
- Planning preparation requires the exact canonical identity policy and retains
  the callback-free option snapshot before deriving resources. Existing
  workflow-entry, execution-overlay, verify-continuation, external-ingress, and
  filesystem/persistence enforcement remains at its authoritative owner.
- The three-finding SIM-1 stop is recorded in `SIMPLIFICATION.md`: one aliasing,
  one representation-drift, and one coverage-hole finding. The bounded repairs
  passed independent rereview. The complete deleted-test denominator is 99:
  67 public replacements and 32 removed-mechanism tests, with zero knowingly
  uncovered behavior.

## Verification

- Frozen simplification audit: three identical successful runs; all four frozen
  files unchanged from corpus commit
  `144cbbceb7841d31cc5c85fa04ea1a34d89a74ec`.
- Post-repair focused set: 948 passed.
- Core/dispatcher/workflows/interfaces departments: 3,699 passed, 1 skipped,
  1,423 deselected.
- Node-enabled ordinary suite: 5,091 passed, 4 skipped, 28 headed deselected.
- Import boundaries: 11 kept, 0 broken across 75 files and 333 dependencies.
- Relocation audit: eight codec entries, 15 runtime codec calls, and 134 helper
  definitions reduced to zero; production changed +288/-4,084 and tests
  +1,239/-2,873. These are reported trends, not gates.
- `git diff --check` and the final exact-path commit review still run immediately
  before the SIM-1 commit.

## Next safe action

Implement SIM-2 exactly as closed in `SIMPLIFICATION.md`: move the reliable
canonical-byte maximum into `canonical_event_bytes` before any `EventHub`
mutation, remove downstream Python/JavaScript event-body recertification, and
preserve byte-for-byte event-v5 persistence plus the durable history envelope.
Do not change the epoch, event shape, history receipt/hash/watermark logic,
command validation, unrelated views, or any H2 feature.

After SIM-2 passes its frozen/Node/department/ordinary/import gates, run the
disposable `PlanOperation.simplification_probe` exit test. The target is no more
than eight tracked source/test files; revert every probe change and delete its
branch before final closeout.
