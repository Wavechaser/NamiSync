# Session Handoff

Status (2026-09-01): the M1 consolidation pass and its boundary follow-ups are
complete on `milestone1-anthony`. No new feature or task surface was activated,
and there is no active delivery register.

## Delivered

- Removed process-local workflow JSON codecs, payload versions, byte charges,
  and byte-oriented dispatcher custody. Plan, inventory, and standalone
  integrity use detached domain requests; execution uses one typed checkpoint
  and materializes fresh invocation state on each open.
- Removed downstream Python and JavaScript event-body certification. Core owns
  the canonical v5 projection, EventHub owns the reliable-byte wall, history
  validates the same projection at admission and readback, and the browser owns
  only transport/session/sequence/routing/reducer behavior. Persisted bytes,
  schemas, receipts, hashes, and data epoch are unchanged.
- Kept CLI and bridge request bounds, documented workflow-registration
  detachment, removed the duplicate drain sequence ceiling, and left
  `SessionEventView` intentionally outside the bridge's partial validator table.
  No authority, adoption API, generic freezer, compatibility form, or duplicate
  semantic validator replaced the removed mechanisms.
- Retired the temporary simplification runner, baseline, self-test, and
  department wiring after the final compatibility check. Focused public
  workflow, history, exact-event-byte, and browser tests retain the supported
  behavior; the detailed closed register remains in `SIMPLIFICATION.md`.
- Compacted `CHANGELOG.md` around durable outcomes and owning areas, created the
  standalone `M1 Consolidation` phase, aligned the README phase summaries, and
  removed hard Node-test counts from prose in favor of the executable marker
  policy.

## Verification

- Before retirement, the temporary compatibility audit produced three identical
  runs after the history-admission fix with no baseline drift.
- The database department passed 365 tests; the interfaces department passed
  1,377 with the required unmarked Node probes active.
- The public oracle-replacement set passed 14 tests. The ordinary suite passed
  4,879 tests with four capability skips and 28 headed deselections.
- All 11 import contracts remained kept across 75 files and 334 dependencies.
- The disposable domain-field probe crossed the domain, public view, and real
  dispatcher resume path in six files against a target of eight, then reverted
  cleanly.

## Next safe action

Any new feature, broad authority cleanup, or task-ownership restructure needs
explicit scope and a new finite register. Preserve typed in-process values,
validation at real boundaries, one truth owner, one canonical boundary
projection, opaque dispatcher custody, and no new certification framework.
