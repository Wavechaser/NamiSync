# Session Handoff

Status (2026-08-26): checkpoint 3R.15a is verified for delivery after `4b2af38`.
The browser constant naming and timestamp comment cleanup is complete.
Checkpoint 3.3 remains unstarted and the private legacy decoder remains intact.

`M1_SHELL_H2.md` owns the revised order and full acceptance criteria. Remaining
delivery is 3R.15 documentation and integrated verification. No design decisions
remain open.
Completed causal findings belong in `BUGS.md`, not this handoff. The original
O/S reports and prior verification receipts remain in Git at
`d7673b7:docs/HANDOFF.md`; no separate report archive is needed.

## Authorized Work Still To Deliver

F/S identifiers refer to the original independent reports preserved in Git.

### 3R.15 — Reconcile remaining active-document status

F11/S8 and S18's documentation portion remain for final reconciliation.
Update active status, owning docs, BUGS, README/CHANGELOG, and this handoff
after the authorized deliveries. Do not reintroduce completed finding reports.
Checkpoint 3.3 remains blocked on delivery and independent verification of this
remediation, not on another S5 or identity/epoch design decision.

## Still Unassigned

- The installed-wheel event diagnostic needs coordinated producer/page/parent
  fixture migration: `task-0-item-000` violates v5 HexId; the terminal callback
  still reads `result.items.map` from an item-free summary; expected IDs and
  numeric-byte assumptions also need alignment. Independent probes confirmed
  these predate 3R.8 (at `bd05ff7` and `f96804b`). The failed artifact
  is `build/r38-verification/event-f96804b-1.json`; the directory README retains
  its artifact conventions.
  Passing custody drift evidence is not event or whole-runtime acceptance;
  frozen calibration/holdout/ceiling authority needs no change.
- The adjacent workflow finding from independent 3R.6 review remains
  inspection-only, not separately reproduced or assigned:
  `_settle_execute_resume_failure` can return all exclusions after the
  pre-entry/resume sink rejects one, and emission-error rendering is unguarded.
  Keep it distinct from the repaired ordinary/canceled terminal projection.

## Execution Notes

Deliver one tests-first, independently reviewed and committed checkpoint at a
time, following `M1_SHELL_H2.md`. Keep protected settlement oracle/baseline/
assertions and frozen transport measurement authority unchanged. Use the
required bundled Node for applicable ordinary gates. Do not reuse retained
measurement pytest base directories.

3R.15a verification: the updated source gate failed on the old constant name
before the source change. Focused browser/static gates passed all 93 tests with
required Node, including the timestamp grammar/calendar corpus. The interfaces
department passed all 1,275 tests (3,183 deselected, 44.28 s). Independent narrow
review found no actionable issue. The exact diff changes only the constant's
definition/use, its coordinated test gate, and the comment; validator behavior,
the private legacy decoder, protected settlement, and frozen transport-authority
files are unchanged. The 3R.14 integrated verification receipt is in the prior
commit's handoff.

Old epoch-5 pairs now require the documented explicit archive/reset; no user
databases were deleted or reset. Ledger-v4/history-v6 schemas, the history
contract id, and plan-v5/execution-v6 wire shapes remain unchanged.
The captured MOVE vector is an isolated old-hash replay-gate witness,
not proof of a valid historical first write; a separate valid producer control
and stale/no-write assertion preserve that distinction. `BUGS.md` and owning
component docs now hold the completed identity-hash and S5 dispositions.

Ignored `build/r314-baseline/` contains the independently reviewed one-shot
capture helper and fixed synthetic fixtures. Capture succeeded once at clean
commit `3a1b409`, before any hash changes: 39 byte vectors and two valid
execution-v6 continuations. Its frozen `epoch5-vectors.json` was copied without
replacement to `tests/assets/identity_epoch5_vectors.json`; both have SHA-256
`52f80f8539b863da0a357ba4a47c20a32cb77a5a14db9194d5adf98e31c538d9`.
Never regenerate these old expectations with the new encoder. The ignored
directory README owns capture conventions; no databases were opened or reset.
