# Open-bug sweep (2026-10-01)

Compacted from the working folder `build/open-bugs-20261001/` (35 files, 1.8 MiB); promoted 2026-11-17.

## Contents

Current-state receipt, identity fix, exclusions and reader receipt. The adequacy supplement retains aggregate claim support, identity extracts and explicit provenance limitations.

`summary.md` condenses outcomes, claim-supporting aggregates, input identities, verification and unresolved limitations. It names its source records or immutable Git revision.

`data.json` holds 4 JSON entries, keyed by source path with the original size and SHA-256 (derived entries name their inputs' hashes). Identical files point at the first copy with `same_as`.

- `build/open-bugs-20261001/current.json`
- `build/open-bugs-20261001/exclusions.json`
- `build/open-bugs-20261001/identity-fix.json`
- `build/open-bugs-20261001/reader.json`

## Not retained

Driver error stub, cleanup/doc-link checks, pytest and review caches. Per-run inputs/after snapshots, exit codes, logs and pytest XML, raw/asset/install/cache/temp trees, candidate/baseline source copies and patches, and per-run reports already summarized above.
