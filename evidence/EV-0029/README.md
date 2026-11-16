# R2 third-party notice inputs (2026-11-09)

Compacted from the working folder `build/r2-notices-20261109/` (33 files, 1.4 MiB); promoted 2026-11-17.

## Contents

An authored summary of the notices R2 added and why, its coverage, the pinned upstream inputs with hashes and the committed manifest that is their authority; the CPython install receipt's identity.

`summary.md` condenses outcomes, claim-supporting aggregates, input identities, verification and unresolved limitations. It names its source records or immutable Git revision.

`data.json` holds 1 JSON entries, keyed by source path with the original size and SHA-256 (derived entries name their inputs' hashes). Identical files point at the first copy with `same_as`.

- `build/r2-notices-20261109/python-install-receipt.json`: The CPython install receipt reduced to its identity: id, version, download URL and hash, and index source; aliases and shortcut definitions dropped.

## Not retained

The one-off notice construction scripts (their output and pins are in the committed `tools/packaging/notices/manifest.json` at `1f632b13`), downloaded upstream license pages and source/header copies (hashed in the summary), the composed notices and focused-test XML. Per-run inputs/after snapshots, exit codes, logs and pytest XML, raw/asset/install/cache/temp trees, candidate/baseline source copies and patches, and per-run reports already summarized above.
