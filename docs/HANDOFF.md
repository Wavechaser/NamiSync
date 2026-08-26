# Session Handoff

Status (2026-08-27): delivered checkpoint **3R**, closing the independent review
findings against H2 checkpoints 1–3.2. The compact issue/commit index in
[M1_SHELL_H2.md](M1_SHELL_H2.md#3r-remediate-independent-checkpoint-review-findings)
and the module-first [bugs ledger](BUGS.md) own the details. Checkpoint 3.3
remains unstarted; the safe next step is its separately reviewed private legacy
decoder removal, not a restart of the completed bug hunt.

## Delivered in this bug-hunt session

- Paused the parent delivery after `4c3b5ea`–`7c93380`, investigated both
  external reviews, and delivered 24 small planning/fix/closure commits from
  `989617a` through `bba64ec`. The index includes the oracle repair,
  tests-first 3R.4 rebuild, cancellation follow-up, database admission/read
  cost fixes, S5 store projection, explicit hash projections/epoch 6, and the
  final live-validator naming and strict-Unicode refinements.
- Completed findings are in BUGS, not duplicated here. Original O/S reports
  remain at `d7673b7:docs/HANDOFF.md`; the full pre-condensation checklist and
  prior verification/capture receipts remain at `74abbc6:docs/M1_SHELL_H2.md`
  and `74abbc6:docs/HANDOFF.md`.
- Archived historical M0 criteria in [obsolete/M0_PLAN.md](obsolete/M0_PLAN.md)
  (`6735f8c`), retaining the few unique current rules in their component
  contracts. Relocated all five PoC documents byte-for-byte into
  `obsolete/PoC_import/` (`74abbc6`). Active prose remains authoritative.
- This final documentation pass condenses 3R, aligns the owner documents, and
  records the accepted sorting and integrity additions below. It changes no
  runtime, test, oracle, database, or protected measurement artifact.

## Accepted next-checkpoint additions — not implemented

- **7:** shared server-owned sibling sorting and full plan integration.
  **9:** full inventory integration. New views and reset use canonical path-key
  order; filename, size, and mtime are explicit opt-in sorts. Sort complete
  sibling sets before windowing, with raw numeric values, deterministic ties,
  unavailable values last, and no descendant-derived folder timestamps.
  Selection, collapse, hierarchy, node identity, execution authority/order,
  and recursive action scope are unchanged. Revisions, windows, indexes and
  anchors must agree. Complete production bridge support cannot wait for the
  48rem table's mtime/reset layout. Status/progress sorting, global flat
  sorting, and durable preferences are excluded from M1.
- **10:** fresh rebaseline also admits eligible selected files without evidence.
  It always hashes and conditionally replaces/creates evidence, even for a
  genuine match, and clears verification freshness. Explicit selected scope
  and current-evidence acceptance remain required. Compare-and-accept is
  deferred beyond M1; baseline and verify policy are unchanged. The
  [three-operation table](VERIFIER.md#standalone-operation-policy-checkpoint-10-target)
  distinguishes current behavior from this accepted target.
- H2 7.A, 9.A and 10.A contain acceptance, regression, tests, and independent
  review requirements. Bridge DR-BR-15 owns exact sorting semantics.
  There is no remaining design hold for these additions, S5, or 3R.14.

## Verification and preserved boundaries

This documentation pass verified the 24-commit map, the 51-line 3R section,
all 26 new local links/anchors, and the unchanged runtime/test/tool trees.
Independent sorting, integrity, and closure reviews found only wording issues,
corrected before staging; whitespace validation passed.

The latest behavioral receipt is `bba64ec`: required-Node ordinary suite
**4,498 passed, 4 privilege skips, 28 headed deselected** (194.81 s); six
affected departments **3,511 passed, 1 privilege skip**; import architecture
**11 kept, 0 broken**; protected settlement **30 scenarios × 3** with identical
normalized traces and baseline parity. The later M0/PoC and present closeout
commits are documentation-only; these are retained receipts, not newly run
behavioral or headed acceptance. BR-G-45 and SH-G-15 remain open.

For runtime work, continue one tests-first, independently reviewed and
committed checkpoint at a time. Preserve the protected settlement
oracle/baseline/assertions and frozen transport authority; no new oracle
defect is demonstrated by this documentation pass. Use required bundled Node
for applicable gates and fresh measurement directories.

The active pair remains ledger v4/history v6, shared data epoch 6. Old epoch-5
pairs require the documented explicit paired archive/reset; no user database
was reset or deleted. S5 keeps continuations process-local and offers stores
only payload-free projections; M2 restart requires its separately protected
continuation design, as recorded in [DISPATCHER.md](DISPATCHER.md).
The frozen old-byte witness `tests/assets/identity_epoch5_vectors.json` must
not be regenerated with the new encoder. Its SHA-256 remains
`52f80f8539b863da0a357ba4a47c20a32cb77a5a14db9194d5adf98e31c538d9`;
the old handoff retains capture provenance and the MOVE/surrogate witness
qualifications. This pass launches no runtime verification processes.

## Other context outside the closed 3R findings

- The installed-wheel event diagnostic's producer/page/parent fixture
  migration remains unassigned, not current-v5 timing acceptance. Its invalid
  HexId, old terminal-item access, and numeric-byte assumptions predate 3R.8;
  Bridge BR-G-42 owns that disposition. Historical probe/artifact details are
  in `74abbc6:docs/HANDOFF.md`; protected calibration authority is unaffected.
- The adjacent `_settle_execute_resume_failure` pre-entry/resume sink concern
  remains inspection-only, not separately reproduced or assigned. It is not
  the repaired ordinary/canceled terminal projection. Retain that distinction
  rather than silently adding it to checkpoint 3.3 or calling it fixed.
