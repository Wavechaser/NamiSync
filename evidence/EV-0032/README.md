# Release repair R3 renewal, resource collections and package 04 at cfeac2d9 (2026-11-10)

Compacted from the working folder `build/m1-release-repair-20261110/` (629 files, 71.0 MiB); promoted 2026-11-17.

## Contents

R3 identity, profile, commands, collection index/validation and review (the validated compact authority is committed under `tests/interfaces/web/`); Resources03/04 identities, validations and reviews, the payload failure mirror, the package-04 comparison and review, and the rail-click probe result.

`notes.md` concatenates 4 text file(s) verbatim:

- `build/m1-release-repair-20261110/acceptance/20261110-04/package/artifact-comparison-review.md`
- `build/m1-release-repair-20261110/acceptance/20261110-04/resources/review.md`
- `build/m1-release-repair-20261110/renewal/r3-review.md`
- `build/m1-release-repair-20261110/renewal/resources-review.md`

`data.json` holds 14 JSON entries, keyed by source path with the original size and SHA-256 (derived entries name their inputs' hashes). Identical files point at the first copy with `same_as`.

- `build/m1-release-repair-20261110/acceptance/20261110-03/r3/before-collection.json`
- `build/m1-release-repair-20261110/acceptance/20261110-03/r3/br-g-42/index.json`
- `build/m1-release-repair-20261110/acceptance/20261110-03/r3/br-g-42/validation.json`
- `build/m1-release-repair-20261110/acceptance/20261110-03/r3/commands.jsonl`
- `build/m1-release-repair-20261110/acceptance/20261110-03/r3/identity.json`
- `build/m1-release-repair-20261110/acceptance/20261110-03/r3/reference-profile.json`
- `build/m1-release-repair-20261110/acceptance/20261110-03/resources/identity.json`
- `build/m1-release-repair-20261110/acceptance/20261110-03/resources/payload-failure-mirror.json`
- `build/m1-release-repair-20261110/acceptance/20261110-03/resources/validation.json`: Kept as a failure record, apart from acceptance: declaration, budgets, verdict, missing runs and DevTools overhead; every run's checks (value, budget, pass) and scalar peaks; then the failed predicates and invalid runs listed explicitly. Per-window sample vectors and post-close series dropped.
- `build/m1-release-repair-20261110/acceptance/20261110-04/package/identity.json`
- `build/m1-release-repair-20261110/acceptance/20261110-04/package/independent-comparison-02.json`
- `build/m1-release-repair-20261110/acceptance/20261110-04/resources/identity.json`
- `build/m1-release-repair-20261110/acceptance/20261110-04/resources/validation.json`: Kept as a failure record, apart from acceptance: declaration, budgets, verdict, missing runs and DevTools overhead; every run's checks (value, budget, pass) and scalar peaks; then the failed predicates and invalid runs listed explicitly. Per-window sample vectors and post-close series dropped.
- `build/m1-release-repair-20261110/portable/rail-click-probe-20261110-02/probe-result.json`

## Not retained

Five 3.2 MiB bridge-event and five history raw reports (hashes are in the committed validation), the payload `failure.png` (supports one PERFORMANCE sentence; the failure mirror records the state; user, 2026-11-17), schedule samples (up to 5 MiB per run), collector stdout, package outputs and build logs, probe samples. Per-run inputs/after snapshots, exit codes, logs and pytest XML, raw/asset/install/cache/temp trees, candidate/baseline source copies and patches, and per-run reports already summarized above.
