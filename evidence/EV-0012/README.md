# Copy/verification/host-retention investigation (2026-11-06)

Compacted from the working folder `build/copyonly-20261106/` (41 files, 0.4 MiB); promoted 2026-11-17.

## Contents

The copy timings aggregated by revision and mode, and the GUI runs' per-owner call and time ranges. The adequacy supplement retains aggregate claim support, identity extracts and explicit provenance limitations.

`summary.md` condenses outcomes, claim-supporting aggregates, input identities, verification and unresolved limitations. It names its source records or immutable Git revision.

`data.json` holds 2 JSON entries, keyed by source path with the original size and SHA-256 (derived entries name their inputs' hashes). Identical files point at the first copy with `same_as`.

- `build/copyonly-20261106/copy.jsonl`: The 16 comparison rows aggregated by revision and mode: count, matched files and ranges of each timing.
- `build/copyonly-20261106/gui-summary.json`: The six GUI runs' per-owner call vectors aggregated: elapsed range and, per owner, call-count, wall-second and CPU-second ranges.

## Not retained

The 16 individual copy rows and six individual GUI run vectors, per-run call traces for hidden/visible/delay variants. Per-run inputs/after snapshots, exit codes, logs and pytest XML, raw/asset/install/cache/temp trees, candidate/baseline source copies and patches, and per-run reports already summarized above.
