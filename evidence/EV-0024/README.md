# Release distribution census at b3095886 (2026-11-04)

Compacted from the working folder `build/m1-release-20261104/` (117 files, 4.0 MiB); promoted 2026-11-17.

## Contents

The census producer, its review and a compacted census.

`notes.md` concatenates 1 text file(s) verbatim:

- `build/m1-release-20261104/distribution/census.py`

`data.json` holds 2 JSON entries, keyed by source path with the original size and SHA-256 (derived entries name their inputs' hashes). Identical files point at the first copy with `same_as`.

- `build/m1-release-20261104/distribution/census.json`: Compacted: collections over 2048 bytes of JSON become counts with per-field ranges or value counts, plus the collection's size and SHA-256.
- `build/m1-release-20261104/distribution/review.json`

## Not retained

Repeatable-build attempts, native profiles and smoke/artifact checks. Per-run inputs/after snapshots, exit codes, logs and pytest XML, raw/asset/install/cache/temp trees, candidate/baseline source copies and patches, and per-run reports already summarized above.
