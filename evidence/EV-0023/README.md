# R2 distribution census, attempt 04 (2026-11-09)

Compacted from the working folder `build/m1-r2-20261109/` (117 files, 28.1 MiB); promoted 2026-11-17.

## Contents

Attempt-04 package checksums and build environment; the census identities, owner counts, all 51 notice records and reconciliation counts; source/bundle/native-origin identities as counts and hashes; and the bootloader sources grouped by distinct notice.

`notes.md` concatenates 2 text file(s) verbatim:

- `build/m1-r2-20261109/attempt-04/SHA256SUMS.txt`
- `build/m1-r2-20261109/attempt-04/build-environment.txt`

`data.json` holds 5 JSON entries, keyed by source path with the original size and SHA-256 (derived entries name their inputs' hashes). Identical files point at the first copy with `same_as`.

- `build/m1-r2-20261109/attempt-04/bundle-identity.json`: Per-file bundle hashes replaced by the file count and a hash over the full mapping; the census owner counts and the archive SHA-256 identify the bundle.
- `build/m1-r2-20261109/attempt-04/distribution-census.json`: Bundle (436) and embedded-input (773) inventories replaced by counts by kind and owner, notice coverage and reconciliation checks; identities, owner counts and all 51 notice records kept.
- `build/m1-r2-20261109/attempt-04/native-origins.json`: The 133 native-origin records summarized by kind and coarse origin distribution; detailed source paths replaced by the records' hash.
- `build/m1-r2-20261109/attempt-04/source-identity.json`: The 350 per-file source hashes replaced by their count and a hash over the mapping; commit, interpreter, platform, SOURCE_DATE_EPOCH and dependency pins kept.
- `build/m1-r2-20261109/bootloader-source-audit.json`: The 45 bootloader source files grouped by their distinct notice sets (file names kept for sets of up to ten files); per-file hashes and URLs replaced by the pinned upstream prefix and a hash over the records.

## Not retained

Packages and executables, the per-file bundle (436), source (350), embedded-input (773) and native-origin (133) inventories (each hashed), the study's operational README, checkout identities of other attempts and smoke profiles. Per-run inputs/after snapshots, exit codes, logs and pytest XML, raw/asset/install/cache/temp trees, candidate/baseline source copies and patches, and per-run reports already summarized above.
