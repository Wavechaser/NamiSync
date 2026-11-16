# Continuous-scroll window study SW (2026-10-09)

Compacted from the working folder `build/scroll-window-study-20261009/` (522 files, 92.5 MiB); promoted 2026-11-17.

## Contents

README, integration, diagnostic accounting, host profile and the SW summary's per-workload statistics.

`notes.md` concatenates 3 text file(s) verbatim:

- `build/scroll-window-study-20261009/README.md`
- `build/scroll-window-study-20261009/integration.md`
- `build/scroll-window-study-20261009/sw-context-diagnostic-accounting.md`

`data.json` holds 2 JSON entries, keyed by source path with the original size and SHA-256 (derived entries name their inputs' hashes). Identical files point at the first copy with `same_as`.

- `build/scroll-window-study-20261009/c5-host-profile.json`
- `build/scroll-window-study-20261009/sw-summary-01.json`: Per matrix and workload, each metric's count, median, minimum and maximum; the raw per-run values (including thousands of frame intervals), per-child groups and observed profile/runtime duplicates per matrix dropped. The matrices' input hashes and the matched profiles and runtimes are kept.

## Not retained

Raw per-run values and frame-interval vectors and per-child groups in the SW summary, per-run reports (up to 10 MiB), raw trees, syntax copies and recovery patches. Per-run inputs/after snapshots, exit codes, logs and pytest XML, raw/asset/install/cache/temp trees, candidate/baseline source copies and patches, and per-run reports already summarized above.
