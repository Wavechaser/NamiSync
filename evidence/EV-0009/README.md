# November bug hunt: GUI ingress and CLI encoding fixes (2026-11-04)

Compacted from the working folder `build/bughunt-20261104/` (21 files, 0.0 MiB); promoted 2026-11-17.

## Contents

The ingress receipt, the A2 reproduction, final manifest and final focused/department results.

`data.json` holds 6 JSON entries, keyed by source path with the original size and SHA-256 (derived entries name their inputs' hashes). Identical files point at the first copy with `same_as`.

- `build/bughunt-20261104/evidence/adapters-gui-ingress-receipt.json`
- `build/bughunt-20261104/evidence/fix-a2-department-final.json`
- `build/bughunt-20261104/evidence/fix-a2-final-manifest.json`
- `build/bughunt-20261104/evidence/fix-a2-focused-final.json`
- `build/bughunt-20261104/evidence/fix-a2-original-final.json`
- `build/bughunt-20261104/evidence/fix-a2-original-repro.json`

## Not retained

Red, green-seam and intermediate focused/department runs and their logs. Per-run inputs/after snapshots, exit codes, logs and pytest XML, raw/asset/install/cache/temp trees, candidate/baseline source copies and patches, and per-run reports already summarized above.
