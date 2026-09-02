# Session Handoff

Status (2026-09-03): LC-1a and LC-1b are complete on
`milestone1-anthony`. A separate pre-LC-2 stabilization commit is the current
`HEAD`; LC-2 is authorized and has not yet changed production.

## Stabilization outcome

- `TaskLifecycle` plan retirement now has one tolerant exact-token claim
  acquisition. Service cleanup and explicit plan drop both retire selection
  state only for the exact plan token, while runtime calls remain outside the
  service lock.
- The lifecycle structural guard rejects cleanup progress/cursor vocabulary
  without freezing imports or complete private field sets. A separate guard
  retains the no-delivery/no-observer-resource contract, and the public task
  port surface remains exact.
- Cleanup replay continues to call the fixed observer, Dispatcher, detail, and
  plan owners from the beginning. Tests now state the real contract: calls may
  repeat, completed observable transitions may not.
- The duplicate rollback test name is disambiguated. Every current-owner test
  reference in `docs/TASK_LIFECYCLE_TEST_LEDGER.md` resolves; historical names
  remain only as previous-test/crosswalk evidence.
- The detailed LC-2 observer-lifetime checkpoint was recovered from the
  historical `.codex` plan into the sole active register. It distinguishes
  external release from callback self-release and retained adopted streams
  from transient Dispatcher offers. The `.codex` plan remains untouched.
- The adapter-local exception-graph helper remains an intentional duplicate:
  the strong drain import contract makes the core helper unreachable, and this
  stabilization does not relax that boundary.

## Verification

- Focused lifecycle/service/bridge: `179 passed`.
- Ordinary suite with bundled Node:
  `4944 passed, 4 skipped, 28 deselected`.
- Frozen task-lifecycle T1 corpus: exact baseline match.
- Import law: `12 kept, 0 broken`.
- Active current-owner ledger references: `119 checked, 0 missing`.
- `git diff --check`: clean apart from expected line-ending notices.

## Next action

Begin LC-2 exactly as specified in
`docs/TASK_LIFECYCLE_SIMPLIFICATION.md`: move retained observation lifetime
from `service.py` to `session_observer.py`, preserve CLI push timing and web
delivery withdrawal, and keep whole-operation application cleanup replay free
of observer-internal progress. Commit LC-2 only after its focused barriers,
T1/T2, ordinary, and import-law gates pass.

The old recovery/WIP refs remain isolated and are not review units; never
merge or cherry-pick them.
