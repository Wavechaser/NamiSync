# Executor simplification, differential and direct-write measurements (2026-09-29)

Compacted from the working folder `build/executor-simplification-20260929/` (1,145 files, 58.9 MiB); promoted 2026-11-17.

## Contents

Study README, ceiling results and device profile, the archived reproduction's per-case outcomes on both sides and the final regression gate cited by BUGS, and the result-8 measured comparisons, band summaries, commands and host identities cited by PERFORMANCE. The adequacy supplement retains aggregate claim support, identity extracts and explicit provenance limitations.

`summary.md` condenses outcomes, claim-supporting aggregates, input identities, verification and unresolved limitations. It names its source records or immutable Git revision.

`notes.md` concatenates 4 text file(s) verbatim:

- `build/executor-simplification-20260929/README.md`
- `build/executor-simplification-20260929/ceilings/results.md`
- `build/executor-simplification-20260929/differential/result5-final-focused.log`
- `build/executor-simplification-20260929/measurements/result8-b9c4ad3e-20260930-201114-989e90d9-dependencies.txt`

`data.json` holds 15 JSON entries, keyed by source path with the original size and SHA-256 (derived entries name their inputs' hashes). Identical files point at the first copy with `same_as`.

- `build/executor-simplification-20260929/ceilings/threshold-device-profile-20260930.json`
- `build/executor-simplification-20260929/measurements/result8-b9c4ad3e-20260930-201114-989e90d9-commands.json`
- `build/executor-simplification-20260929/measurements/result8-b9c4ad3e-20260930-201114-989e90d9-comparison.json`: The 493-entry candidate dependency hash inventory replaced by its count and a hash; the measured rows, revisions, candidate status and limits kept.
- `build/executor-simplification-20260929/measurements/result8-b9c4ad3e-20260930-201114-989e90d9-cpu.json`
- `build/executor-simplification-20260929/measurements/result8-b9c4ad3e-20260930-201114-989e90d9-disks.json`
- `build/executor-simplification-20260929/measurements/result8-b9c4ad3e-20260930-201114-989e90d9-drive-map.json`
- `build/executor-simplification-20260929/measurements/result8-b9c4ad3e-20260930-201114-989e90d9-fg-1000x4KiB.json`: Per-sample records dropped; configuration, batch preparation/validation timings and the band summary kept.
- `build/executor-simplification-20260929/measurements/result8-b9c4ad3e-20260930-201114-989e90d9-fg-1x4GiB.json`: Per-sample records dropped; configuration, batch preparation/validation timings and the band summary kept.
- `build/executor-simplification-20260929/measurements/result8-b9c4ad3e-20260930-201114-989e90d9-fg-4x128MiB.json`: Per-sample records dropped; configuration, batch preparation/validation timings and the band summary kept.
- `build/executor-simplification-20260929/measurements/result8-b9c4ad3e-20260930-201114-989e90d9-fg-512x128KiB.json`: Per-sample records dropped; configuration, batch preparation/validation timings and the band summary kept.
- `build/executor-simplification-20260929/measurements/result8-b9c4ad3e-20260930-201114-989e90d9-fg-64x4MiB.json`: Per-sample records dropped; configuration, batch preparation/validation timings and the band summary kept.
- `build/executor-simplification-20260929/measurements/result8-b9c4ad3e-20260930-201114-989e90d9-os.json`
- `build/executor-simplification-20260929/measurements/result8-b9c4ad3e-20260930-201114-989e90d9-predecessor-comparison.json`
- `build/executor-simplification-20260929/measurements/result8-b9c4ad3e-20260930-201114-989e90d9-volumes.json`
- `build/executor-simplification-20260929/differential/result3a-archive-outcomes.json`: Paired baseline/candidate case dumps reduced to each case's status, outcome, reason and recording on both sides and whether they agree.

## Not retained

The 493-entry candidate dependency hash inventory (hashed), per-sample band records, the paired differential case dumps (effects, details, files), repeated A/B and idle-recheck runs, threshold samples, ACL fixture restoration dumps, closeout copies of CHANGELOG/README and checkout provenance listings. Per-run inputs/after snapshots, exit codes, logs and pytest XML, raw/asset/install/cache/temp trees, candidate/baseline source copies and patches, and per-run reports already summarized above.
