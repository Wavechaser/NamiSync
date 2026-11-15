# M1 documentation compaction verification (2026-11-11)

Receipts for the approved compaction of M1_PLAN, PERFORMANCE, CHANGELOG and
DESKTOP_UI (`c27da6aa`) and its DESKTOP_UI follow-up, compacted from the working
folder `build/mop-up-survey-20261111/`. Every other file keeps its original bytes.

- `documentation-survey.md`: the editorial proposal the user approved.
- `documentation-disposition-summary.json`: block counts per disposition and
  before/after SHA-256 for each document.
- `documentation-verification.json`, `readme-verification.json`,
  `documentation-review.md`: integrated checks and the adversarial review.
- `ui-round2-composition.json`, `ui-round2-verification.json`,
  `ui-round2-review.md`: the DESKTOP_UI follow-up's checks and review.

Not retained: the per-block disposition ledgers (1,356 and 215 blocks). Each
disposition carried one fixed reason sentence, so the summary holds everything
except the block-to-destination map, which Git reproduces from the before text
at `f80773b5` and the result at `c27da6aa`. Per-range, per-link and per-block
hash listings and the producing scripts were dropped for the same reason.
