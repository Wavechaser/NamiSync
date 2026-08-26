# Session Handoff

Status (2026-08-26): checkpoint 3R.15 is complete after `d05995d`.
All authorized behavior fixes and the browser cleanup are committed; active
documentation is reconciled. Checkpoint 3.3 remains unstarted and the private
legacy decoder remains intact.

`M1_SHELL_H2.md` owns the checkpoint boundaries and full acceptance criteria.
No design decisions remain open. The safe stop is before checkpoint 3.3; do not
fold the two unassigned findings below into its legacy-source removal.
Completed causal findings belong in `BUGS.md`, not this handoff. The original
O/S reports and prior verification receipts remain in Git at
`d7673b7:docs/HANDOFF.md`; no separate report archive is needed.

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

Final verification with required Node: the ordinary suite passed 4,426 tests
with four skips and 28 headed tests deselected (193.71 s). All four skips are
unavailable Windows symlink/reparse privileges (`WinError 1314`), not skipped
Node gates. Import architecture kept all 11 rules. The protected settlement
check passed all 30 scenarios three times with identical normalized traces and
baseline parity. Source/status scans and diff checks passed. Independent final
documentation review and a separate S5 cross-contract check found no actionable
issue. Earlier checkpoint receipts remain in their commits rather than
accumulating here.

The closure changes documentation only. Protected settlement and frozen
transport-authority files are unchanged, as is the frozen identity artifact
below. No new headed acceptance is claimed; BR-G-45 and SH-G-15 remain open.
No verification process remains running.

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
directory README owns capture conventions; the capture opened or reset no
databases.
