# M1 documentation compaction verification (2026-11-11)

Receipts for the approved compaction of M1_PLAN, PERFORMANCE, CHANGELOG and
DESKTOP_UI (`c27da6aa`) and its DESKTOP_UI follow-up, compacted from the working
folder `build/mop-up-survey-20261111/`. Every other file keeps its original bytes.

- `documentation-survey.md`: the editorial proposal the user approved.
- `docs-before-hashes.json`: hashes of the exact before text; the text itself
  is in Git at `f80773b5`.
- `documentation-disposition-summary.json`, `documentation-final-link-delta.json`,
  `documentation-link-changes.json`, `preserved-performance-ranges.json`:
  disposition totals, link and retained-method accounting.
- `documentation-verification.json`, `readme-verification.json`,
  `documentation-review.md`: integrated checks and the adversarial review.
- `ui-round2-*`: the DESKTOP_UI follow-up dispositions, checks and review.
- `record_document_dispositions.py`, `verify_documentation.py`,
  `verify_ui_round2.py`: producers of the accounting and checks.

Not retained here: the per-block disposition ledger
`documentation-dispositions.jsonl` (1.6 MiB, over the per-file cap); its
summary above carries the totals.
