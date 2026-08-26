# Session Handoff

Status (2026-08-26): checkpoint 3R.S5 is verified for delivery after `6cdfd08`.
Next is the guarded epoch-5 baseline capture, then revised 3R.14 implementation.
The remaining identity/epoch decisions below are ratified, not implemented.
Checkpoint 3.3 remains unstarted and the private legacy decoder remains intact.

`M1_SHELL_H2.md` owns the revised order and full acceptance criteria. Remaining
delivery is revised 3R.14, 3R.15a, then 3R.15.
Completed causal findings belong in `BUGS.md`, not this handoff. The original
O/S reports and prior verification receipts remain in Git at
`d7673b7:docs/HANDOFF.md`; no separate report archive is needed.

## Authorized Work Still To Deliver

The JavaScript follow-ups below
come from the user's post-3R.13 review and inspection at `d7673b7`.
F/S identifiers refer to the original independent reports preserved in Git.

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

S5 verification: the tests-first reproducer retained the admission payload
after completed shutdown and failed at that assertion. Final focused run:
338 passed. Core/dispatcher/workflows/database/interfaces neighborhood:
3,330 passed, 1 skipped. Independent review corrected a swallowed callback
assertion; the focused rerun and final ordinary suite include that correction.
Ordinary suite with required Node: 4,325 passed, 4 expected skips, 28 headed
tests deselected (219.46 s). Import architecture: all 11 rules kept. Independent
source, lifecycle/fault-test, and owning-document review found no remaining
actionable issue. Protected settlement and transport-authority files are
unchanged. `BUGS.md` and `DISPATCHER.md` own the causal disposition and storage
contract; this handoff no longer lists S5 as an open finding.

Ignored `build/r314-baseline/` contains an independently reviewed capture script and
fixed synthetic fixtures prepared for 3R.14. No capture has run. After S5's
clean commit, inspect/run that guarded one-shot helper before changing any hash
encoder; its README owns artifact conventions and the no-overwrite rule.
