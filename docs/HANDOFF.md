# Session Handoff

Status (2026-08-26): checkpoint 3R.14 is verified for delivery after `3a1b409`.
Closed hash projections and the coordinated epoch-6 cut are implemented.
Checkpoint 3.3 remains unstarted and the private legacy decoder remains intact.

`M1_SHELL_H2.md` owns the revised order and full acceptance criteria. Remaining
delivery is 3R.15a, then 3R.15. No design decisions remain open.
Completed causal findings belong in `BUGS.md`, not this handoff. The original
O/S reports and prior verification receipts remain in Git at
`d7673b7:docs/HANDOFF.md`; no separate report archive is needed.

## Authorized Work Still To Deliver

The JavaScript follow-ups below
come from the user's post-3R.13 review and inspection at `d7673b7`.
F/S identifiers refer to the original independent reports preserved in Git.

### 3R.15a — Narrow JavaScript comment/name cleanup

Correct `bridge.js`'s `isUtcTimestamp` comment: without multiline mode,
JavaScript `$` matches only the end, not before a final newline.
Rename the live `DORMANT_CORE_EVENT_SCHEMA_VERSION` constant to
`CORE_EVENT_SCHEMA_VERSION` at both uses and update the exact name/count gate
in `tests/interfaces/web/_frontend_test_support.py`. Preserve validator
behavior and the private legacy decoder reserved for checkpoint 3.3.

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

3R.14 verification: the tests-first codec gate failed 21 cases with six positive
controls passing; the two epoch-cut cases also failed before implementation.
Initial focused green: 350 passed. Expanded core/command/native files: 254
passed, one expected skip; all 28 projection subclass/lookalike guards passed
their focused rerun. Operation receipt tests: 20 passed. Existing recorder/
planner/package controls: 70 passed; full workflow file: 27 passed.
Core/planner/database/workflows neighborhood: 2,081 passed, one expected skip.
Final ordinary suite with required Node: 4,426 passed, four expected skips,
28 headed tests deselected (220.30 s). Import architecture: all 11 rules kept.
Protected settlement check: all 30 scenarios passed three times with identical
normalized traces and baseline parity. Independent source, compatibility-test,
and documentation review found no remaining actionable issue; protected
settlement and frozen transport-authority files are unchanged.

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
