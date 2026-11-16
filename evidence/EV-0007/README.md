# Bridge command-catalog repair (2026-10-04)

Compacted from the working folders `build/bridge-catalog-20261004`, `build/gui-refinements-20261004/` (18 files, 3.4 MiB); promoted 2026-11-17.

## Contents

The installed bridge-event case verdicts and the original command-catalog source comparison.

`data.json` holds 2 JSON entries, keyed by source path with the original size and SHA-256 (derived entries name their inputs' hashes). Identical files point at the first copy with `same_as`.

- `build/bridge-catalog-20261004/installed.json`: Compacted: collections over 2048 bytes of JSON become counts with per-field ranges or value counts, plus the collection's size and SHA-256.
- `build/gui-refinements-20261004/rf2-command-catalog-audit.json`

## Not retained

Raw bridge samples (hash kept), doc-link and cleanup checks, caches. Per-run inputs/after snapshots, exit codes, logs and pytest XML, raw/asset/install/cache/temp trees, candidate/baseline source copies and patches, and per-run reports already summarized above.
