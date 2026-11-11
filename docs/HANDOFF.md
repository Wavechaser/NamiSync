# Latest session — documentation commit and BUGS access layer, 2026-11-11

Committed the preceding documentation cleanup as c27da6aa, then implemented the
user-approved BUGS access layer as a separate independently reviewed checkpoint.
No product behavior, defect classification, evidence authority or build cleanup
changed. BUGS remains the canonical module-first log.

## Delivery

- Add immutable BUG-0001 through BUG-0319 anchors, initially assigned in source
  order. Preserve every original paragraph, metadata value and owner/scope heading.
  BUGS owns allocation, retention and sibling-analysis conventions; TOOLS owns use.
- `python -m tools.bugs` validates the whole log before filtering, then produces
  complete Markdown/JSONL records with source spans, stable links and source hash.
  Owner/scope/category, ID/status/severity and full-text filters compose across
  owners; explicit offsets/limits batch whole records. No implicit truncation.
- Reject missing/duplicate/orphan IDs, malformed/unaccounted records and nested
  entries. Preserve compound statuses/date qualifiers. Exports create new files
  exclusively; no automatic edit, semantic classification or maintained catalog.
- A trial authority+path search returns 15 full records across eight owner groups.
  The two same-owner/date/category records remain distinct as BUG-0307/0308.
  Candidates still require full-entry and current-code review for common cause.
- Add the requested Headed GUI test harness heading above its existing TOOLS
  instructions; no harness behavior or acceptance guidance changed.

## Evidence and verification

Evidence: build/mop-up-survey-20261111/bug-access-review.md and
bug-access-verification.json. Removing only new anchors/access conventions
reproduces c27da6aa's original BUGS text exactly; all 319 records/IDs and 498
local documentation links pass. The one-time migration map and sample exports
are ignored evidence, not maintained authorities. Diff checks pass.

All 24 final access tests pass under the retained release-checkout Python 3.15.2
while importing this working tree. Ordinary coverage totals 6,564 passes and
four symlink-privilege skips; 35 headed cases remain deselected. The verification
receipt accounts for every node: unaffected ordinary passes, all 95 previously
failed/error nodes rerun with corrected external temp, then final access tests
after phrase/link corrections. Receipts: bugs-ordinary-host, bugs-affected-rerun
and bugs-phrase-final.{log,xml}. No test or product weakening.

Use temporary directories outside the repository for corpus/custody tests;
their location guards reject build-local temps. The main .venv is still 3.13.17
and is not the selected release interpreter. Restricted native junction/temp
access caused earlier fixture failures; failed/interrupted attempts remain
documented in the review. Task-created fixtures were removed; receipts retained.

A fresh subagent independently verified migration preservation and adversarially
reviewed the tool, then passed the phrase-search delta and reran all 24 final
focused tests on Python 3.15.2. No unresolved review findings remain.

Earlier documentation receipts certify c27da6aa's editorial checkpoint, including
the final 1,075-line DESKTOP_UI. Their unchanged-BUGS/Markdown-only assumptions
are historical after this migration. Do not rerun old UI composers to overwrite
current docs. No push, publication or tester delivery occurred.

## Retained operational context

Further build cleanup is paused at its last 4.80 GiB / 99,527-file census;
do not retry denied rows or remove worktrees. Evidence-storage/retention design
is undecided. Keep F:\NamiSyncExecutorBenchSource, the user's H:\test_dir\source
and target play directories including trash, all three detached worktrees and
their runtime, reconstruction assets, release evidence and tester material.
Six codex branches and 61 external resource roots were already cleared; worktree
removal (Tier C) was not authorized.

Final candidate b0a3fe13 / Package05, ZIP SHA-256
652c55ca3c2ace0903732490ead0b907ac726dba5af4155aa5345db80c8e9efc.
Keep dist/v0.1.0 and R5 delivery. M1 headings remain pending external delivery;
the separate README rewrite remains outside this checkpoint. Microsoft terms
remain maintainer wording without legal review.
