# Post-M1 build and external cleanup receipts (2026-11-11 – 2026-11-14)

Compacted from the working folder `build/mop-up-survey-20261111/` at the end of
the cleanup. Every other file here keeps its original bytes.

- `report.md`, `survey-summary.json`: the original read-only survey.
- `external-cleanup-*.json`, `branch-audit.json`, `cleanup-verification.json`:
  61 external resource roots and six codex branches removed on 2026-11-11.
- `cleanup.md`: chronology of every build round and its authorization.
- `build-report.md`: per-round plans, holds and measurements.
- `tierab-*.json`, `round5-result.json`, `round6-*.json`, `round7-*.json`:
  per-round plans and receipts (planned/removed/denied counts, census after).
- `policy-cited.csv`: every `build/` path cited by tracked files when the
  retention policy was applied, with its citers and retained bytes.
- `*.py`, `*.ps1`: the survey, planners, executor and hold checks that
  produced the receipts.

Not retained: per-row manifests and the deletion journal (round manifests
5–33 MB each, journal 120 MB) and full census CSVs. The receipts carry their
counts; the planners show the rules. After round 7, 1,347 files denied by
Codex-sandbox ACLs (every earlier denied row still present was re-planned in
round 7) remained for an elevated rerun.
