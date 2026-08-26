# Session Handoff

Status (2026-08-27): both hanging fixes are delivered: 3R.15b live v5 naming
(`1c2ca16`) and 3R.14a strict Unicode-scalar boundaries (`bba64ec`). The M0
criteria archive separates historical checklists from active contracts.
Next, relocate `PoC_import` into `obsolete` as its own reviewed documentation
checkpoint.
Integrity policy is held for user consideration; do not change it. Checkpoint
3.3 remains unstarted and the private legacy decoder remains intact.

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

For runtime work, deliver one tests-first, independently reviewed and committed
checkpoint at a time, following `M1_SHELL_H2.md`. Keep protected settlement
oracle/baseline/assertions and frozen transport measurement authority unchanged. Use the
required bundled Node for applicable ordinary gates. Do not reuse retained
measurement pytest base directories.

The retrospective `obsolete/M0_PLAN.md` uses the final pre-M1 snapshot
`5b6a0013098f4e73febd6630831daeaa40abc686`, not M1-amended checklists relabeled
as M0. All 13 extracted acceptance tails match that source exactly apart from
heading depth, line endings, and trailing blank lines, including the original
future/latent qualifications and verification notes. Blame and current-prose
review identified stale criteria; active prose remains authoritative. The few
unique current rules and fixture details stay in `VERIFIER.md`, `DATABASE.md`,
and `RECORDER.md`. Current M1 gates and latent ingest criteria remain in place.
Independent review corrected archive-authority wording; all 22 new local links
resolve, including their section anchors. Active pre-tail prose is unchanged
apart from the five explicit retention insertions in those three documents.
This checkpoint changes documentation only; the runtime verification below
therefore still applies to the unchanged code.

3R.14a tests-first Unicode/warning regressions failed 64 cases against the old
runtime, with five controls passing. Strict encoding/decoding and warning
construction made the focused checks pass. The complete five-module run then
passed 426 tests with one reparse-privilege skip (9.17 s); its initial four
setup failures were corrected by moving the existing malformed-value injection
from the now-validated warning constructor to an unvalidated evidence field,
preserving the recorder's independent refusal/no-write assertions.

With required Node, the six affected departments passed 3,511 tests with one
skip and 1,018 deselected (85.45 s). The ordinary suite passed 4,498 tests with
four skips and 28 headed tests deselected (194.81 s). All skips are unavailable
Windows symlink/reparse privileges (`WinError 1314`), not skipped Node gates.
Import architecture kept all 11 rules. The protected settlement check passed
30 scenarios three times with identical normalized traces and baseline parity.
Independent source/test review found no actionable issue; documentation review
caught stale planner/features wording, corrected before final review.
The naming checkpoint's own receipt remains in `1c2ca16:docs/HANDOFF.md`.

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
component docs now hold the completed identity-hash, Unicode, and S5 dispositions.
The Unicode refinement adds no reset: valid-Unicode bytes are unchanged.
Captured surrogate preimages remain historical refusal witnesses; the two old
inventory vectors contain malformed optional warning detail, now omitted at
construction, so even their identityless old receipt conflicts without writes.

Ignored `build/r314-baseline/` contains the independently reviewed one-shot
capture helper and fixed synthetic fixtures. Capture succeeded once at clean
commit `3a1b409`, before any hash changes: 39 byte vectors and two valid
execution-v6 continuations. Its frozen `epoch5-vectors.json` was copied without
replacement to `tests/assets/identity_epoch5_vectors.json`; both have SHA-256
`52f80f8539b863da0a357ba4a47c20a32cb77a5a14db9194d5adf98e31c538d9`.
Never regenerate these old expectations with the new encoder. The ignored
directory README owns capture conventions; the capture opened or reset no
databases.
