# Latest session — evidence promotion, 2026-11-17

After the user's per-claim adequacy review, all 36 staged candidates were
promoted unchanged as EV-0003–EV-0038 (108 files, 1,147,687 bytes) with
`tools.evidence add`/`seal`. Each record README now names its working source
and promotion date; the candidate-only "claims resting on the source" lists were
dropped (`python -m tools.evidence list` reports citers). The inventory cold
collector moved to `build/inventory-cold/`; `failure.png` and the collector
profile/output got no record (user decisions).

## Changes and verification

- 74 citing lines in BUGS, M1_PLAN, PERFORMANCE, TESTS and TOOLS now link
  records instead of `build/` folders. Retention prose was corrected with each
  repoint: PERFORMANCE no longer promises raw intervals, source manifests,
  schedule samples, R3 full reports, the payload screenshot or result-8 scripts;
  TOOLS' census text names counts/identities instead of paths and hashes, and the
  R2 notices text points at the committed `tools/packaging/notices/manifest.json`
  instead of source/header copies. Allocation, copyonly and exec-time citations
  carry their provenance limits.
- `tools.evidence check`: 38 records, zero problems. No lasting Markdown cites a
  promoted source folder. 361 relative Markdown links resolve; `git diff --check`
  clean. Product tests were unnecessary for documentation and evidence changes.

## Open items

- At the user's request the 42 promoted source folders (named in the records'
  manifest `origin`) and `build/evidence-candidates/` were deleted. Four keep
  only pytest temp residue owned by the Codex sandbox account (731 files,
  18.5 MB; no evidence): `executor-assessment-20260927`, `m1-9-20261001`,
  `post-m1-8-ablation-20260925` and `root-admission-optimization-20260928`.
  Together with the 55 empty `build/move-history-20260925/` folders, they need
  an elevated `Remove-Item -Recurse -Force`.
- At the later `build/` cleanup, keep `build/inventory-cold/` and other
  likely-regenerated working inputs such as the icon archive. M1_PLAN-cited
  early-M2 reference folders (for example `build/ab9-20260926/`) were not part of
  this batch.

Keep `F:\NamiSyncExecutorBenchSource`, the user's `H:\test_dir\source` and
`target` play directories including trash, and `dist/v0.1.0/`. Final package:
`b0a3fe13` / Package05, ZIP SHA-256
`652c55ca3c2ace0903732490ead0b907ac726dba5af4155aa5345db80c8e9efc`.
M1 release headings remain pending external delivery. Unrelated
`docs/M2_PROPOSAL.md` edits remain uncommitted.
