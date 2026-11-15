# Post-M1 build and external cleanup receipts (2026-11-11 – 2026-11-15)

Compacted from the working folder `build/mop-up-survey-20261111/`. Every other
file here keeps its original bytes.

- `report.md`: the original read-only survey of build, external roots and branches.
- `branch-audit.json`, `external-cleanup-result.json`, `cleanup-verification.json`:
  six codex branches and 61 external resource roots removed on 2026-11-11.
- `cleanup.md`: chronology of every build round and its authorization.
- `build-report.md`: per-round plans, holds and measurements.
- `tierab-result.json`, `round5-result.json`, `round6-result.json`,
  `round7-result.json`: per-round counts, denied rows and census after.

Not retained, by the retention policy's per-run/ledger rule: per-row manifests
and the deletion journal, census and citation tables, per-root plans, and the
survey, planner and executor scripts. The receipts carry the counts and each
rule's proof; the scripts only made sense against a build state that no longer
exists. After round 7, 1,347 files held by Codex-sandbox ACLs remained for an
elevated rerun, which uses a reduced kit left in the working folder.
