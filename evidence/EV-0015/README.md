# GUI execution-time trials (2026-11-09)

Compacted from the working folder `build/exec-time-20261109/` (258 files, 13.9 MiB); promoted 2026-11-17.

## Contents

One aggregate over the ten batches: per batch and arm, trial counts, execute-second and peak-MiB ranges, headless verify/CPU ranges, failures, run order and the GUI-minus-headless gap; per arm, the fastest and slowest trial. The adequacy supplement retains aggregate claim support, identity extracts and explicit provenance limitations.

`summary.md` condenses outcomes, claim-supporting aggregates, input identities, verification and unresolved limitations. It names its source records or immutable Git revision.

`data.json` holds 1 JSON entries, keyed by source path with the original size and SHA-256 (derived entries name their inputs' hashes). Identical files point at the first copy with `same_as`.

- `build/exec-time-20261109/batches.json`: The ten batches' 49 trial rows aggregated per batch and arm: trial count, execute-seconds and peak-MiB ranges, headless verify-phase and CPU ranges, failures and leftover processes. Each batch keeps its alternating run order and the GUI-minus-headless median gap (the ordering qualification); each arm keeps its fastest and slowest trial across batches (outliers).

## Not retained

The 49 individual trial rows, per-run samples, thread traces, app/event logs, profiles, batch console logs and the trial scripts. Per-run inputs/after snapshots, exit codes, logs and pytest XML, raw/asset/install/cache/temp trees, candidate/baseline source copies and patches, and per-run reports already summarized above.
