# Session Handoff

Status (2026-09-03): LC-2 is complete on `milestone1-anthony`; its atomic
observer-lifetime commit is the current `HEAD` once this handoff is committed.
LC-3 is the next pending register row.

## LC-2 outcome

- `namisync/interfaces/session_observer.py` now owns `SessionObserver` and its
  private `SessionSubscription`, including adopted streams, sinks, callbacks,
  worker threads, recovery, stop/done state, and release.
- `SessionObserver.adopt` closes a rejected offer and returns no rollback
  capability. `NamiSyncService` retains its public `unsubscribe` surface but
  delegates it, admission rollback, and settlement cleanup to observer
  `release`.
- External release waits for physical worker retirement. Callback self-release
  skips self-join and leaves only the retiring subscription in observer
  custody until unwind, so a concurrent external release remains truthful.
  The established Terminal-event then terminal-record callback pair is
  unchanged.
- Web delivery shutdown remains adapter-local. The strong indirect import
  contract now also prevents drain-side reach into `session_observer`.
- Five obsolete returned-observer-rollback parameter cases were removed and
  two owner-level tests were added. The affected ledger rows are closed; no
  boundary test was deleted.
- The production move is net 56 lines, attributable to explicit self-release
  physical custody. No application cursor/progress, adapter cleanup authority,
  pull loop, delivery queue, or capacity change was introduced.

## Verification

- Focused observer/CLI/lifecycle/host: `298 passed`.
- Interfaces/dispatcher departments with bundled Node:
  `1583 passed, 3390 deselected`.
- Bridge/drain focus: `136 passed`.
- Observer fault/release slice: `54 passed`.
- Ordinary suite with bundled Node:
  `4941 passed, 4 skipped, 28 deselected`.
- Frozen task-lifecycle T1 corpus: exact baseline match.
- Import law: `12 kept, 0 broken`.
- Two independent adversarial reviews: no remaining blocker.

## Next action

Begin LC-3 from the active register. Compose live `SessionRecord` around the
exact frozen `StoredSessionRecord`, preserve constructor/read-only field
compatibility, explicitly accept the registered dataclass-introspection change,
and make no scheduler, condition, concurrency, map, or persistence-byte change.

The historical `.codex` plan remains untouched. Old recovery/WIP refs remain
isolated and are not review units.
