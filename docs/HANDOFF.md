# Session Handoff

Status (2026-08-26): checkpoint 3R.15b completes the live v5 validator-family
and vocabulary rename after the earlier remediation closure at `0886c17`.
The next behavior checkpoint is 3R.14a's strict Unicode-scalar boundary. After
that, audit and archive the M0 criteria, then relocate `PoC_import` into
`obsolete`, as separately reviewed documentation checkpoints. Integrity policy
is held for user consideration; do not change it. Checkpoint 3.3 remains
unstarted and the private legacy decoder remains intact.

`M1_SHELL_H2.md` owns the checkpoint boundaries and full acceptance criteria.
The safe stop is before checkpoint 3.3; do not fold the two unassigned findings
below into its legacy-source removal or these follow-ups.
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

3R.15b verification with required Node: the source gate first rejected the old
function names, then the old vocabulary names. The initial interfaces run
caught a remaining caller in the drain probe; that identifier was corrected.
Focused browser/static/drain checks passed 96 tests (4.41 s); the final
interfaces run passed 1,277 tests, with 3,183 deselected (43.59 s). Independent
review confirmed the production diff is exactly 37 identifier substitutions
across 17 names, with no validator-body changes, name collisions, missed callers,
or weakened gates. Source scans and diff checks passed.

The last ordinary/import/three-run settlement integration receipt remains in
`0886c17:docs/HANDOFF.md`; rerun integration after the Unicode behavior fix.

Protected settlement and frozen transport-authority files are unchanged, as is
the frozen identity artifact below. No new headed acceptance is claimed;
BR-G-45 and SH-G-15 remain open.
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
