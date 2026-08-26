# Session Handoff

Status (2026-08-26): checkpoint 3R.13b is verified for delivery after the
`76d897b` cancellation checkpoint. The next implementation checkpoint is 3R.13c.
The remaining storage/identity decisions below are ratified, not implemented.
Checkpoint 3.3 remains unstarted and the private legacy decoder remains intact.

`M1_SHELL_H2.md` owns the revised order and full acceptance criteria:
3R.13a, 3R.13b, 3R.13c, 3R.S5, revised 3R.14, 3R.15a, then 3R.15.
Completed causal findings belong in `BUGS.md`, not this handoff. The original
O/S reports and prior verification receipts remain in Git at
`d7673b7:docs/HANDOFF.md`; no separate report archive is needed.

## Authorized Work Still To Deliver

The temp-placement and JavaScript follow-ups below
come from the user's post-3R.13 review and inspection at `d7673b7`.
F/S identifiers refer to the original independent reports preserved in Git.

### 3R.13c — Place private copies beside the local database

Validation currently copies full main/WAL contents into an ambient,
environment-selected system temporary directory. Use an owned temporary child
of the database directory, inheriting the required local/non-cloud placement;
refuse creation failure. Document writable-parent requirements, logical I/O,
full-copy scratch cost, cleanup, and possible crash leftovers. Preserve source
main/WAL/SHM/journal no-mutation guarantees; do not claim the parent directory
is unchanged or introduce a new database-size acceptance wall.

### 3R.S5 — Separate payload-free stored records

Original S5 remains open: an accept-first/reject-later store can retain the
admission continuation after live terminal scrubbing. The user approved a
separate frozen stored-record type with no payload field or live-record
reference, explicitly projected at admission and every later write.
Keep live `SessionRecord` and current-process pause/resume, cancellation,
custody, complete result axes, and result-free intermediate terminal records.
Terminal live scrubbing remains required. This is implementation work, not a
remaining design hold or an accepted residual.

For M2, metadata storage is not recovery storage: durable restart/resume needs
a separate protected continuation/recovery contract plus fresh authority and
custody reconciliation. A SQLite replacement alone is insufficient. S5 does
not add M2 recovery, cryptography, all-reference erasure, or an epoch change;
new projections cannot retroactively scrub incompatible old stores.

### Revised 3R.14 — Closed hash projections and coordinated epoch 6

Original F13/S16 remain open. Replace generic dataclass descent in plan and
recorder hashing with explicit owner-defined projections and a closed encoder.
Emit `FileIndex128` as canonical quoted decimal while preserving ordinary
numeric integers, declared hash inputs/encodings, identityless hash bytes, and
the deliberate low-32-bit uppercase volume-serial normalization.
The user approved shared data epoch 5→6 and a changed ledger contract id;
keep ledger-v4/history-v6 shapes, history contract id, and execution-v6 wire
shape. Old pairs require explicit archive/reset, never automatic deletion.
Reset discards app receipts/evidence/history, not source or target files.

The claimed surrogate hash collision was disproved: JSON escapes a literal
backslash before UTF-8 encoding. Preserve the lossless surrogate-escaping rule
and diagnostic tolerance; add the distinguishing regression, not a new strict
surrogate policy that loses scan observations. These choices are ratified but
not yet implemented.

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

3R.13b verification: the tests-first run recorded 29 failures and 6 passing
controls. Independent review strengthened queued-before-close and in-progress
constructor coverage. Final focused run: 43 passed. Database/workflows/
interfaces neighborhood: 2,124 passed. Ordinary suite with required Node:
4,273 passed, 4 expected privilege skips, 28 headed tests deselected (218.09 s).
Independent lifetime/TOCTOU review found no remaining actionable issue.
Standalone admission and protected settlement files are unchanged. The causal
disposition is in `BUGS.md`; `DATABASE.md` owns the exact reader lifetime and
cost diagnostics, so the completed finding is absent from the list above.
