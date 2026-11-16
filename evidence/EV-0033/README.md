# November resource schedule studies (2026-11-06 and 2026-11-08)

Compacted from the working folders `build/resource-study-20261106c`, `build/resource-study-20261108/` (312 files, 102.9 MiB); promoted 2026-11-17.

## Contents

Both FAIL schedules as failure records (every run's checks against budget, failed predicates, invalid runs, verdict); per-function host timers; the host profile's top frames and the heap report's top allocators; the multi-task result. The adequacy supplement retains aggregate claim support, identity extracts and explicit provenance limitations.

`summary.md` condenses outcomes, claim-supporting aggregates, input identities, verification and unresolved limitations. It names its source records or immutable Git revision.

`data.json` holds 6 JSON entries, keyed by source path with the original size and SHA-256 (derived entries name their inputs' hashes). Identical files point at the first copy with `same_as`.

- `build/resource-study-20261106c/multi/runs/heapsample-01/allocation-report.json`: Heap sampling report reduced to heap sizes, sampled total and the top ten self and total allocators; the 30 sampled stacks and remaining rows dropped.
- `build/resource-study-20261106c/multi/runs/multi-02/result.json`
- `build/resource-study-20261106c/profiling/hostprofile-10k.json`: Host sampling profile reduced to its run scalars, threads and the top ten leaf and inclusive frames; the 40 sampled stacks and remaining frame rows dropped.
- `build/resource-study-20261106c/profiling/hosttimers-10k.json`
- `build/resource-study-20261106c/validation.json`: Kept as a failure record, apart from acceptance: declaration, budgets, verdict, missing runs and DevTools overhead; every run's checks (value, budget, pass) and scalar peaks; then the failed predicates and invalid runs listed explicitly. Per-window sample vectors and post-close series dropped.
- `build/resource-study-20261108/validation.json`: Kept as a failure record, apart from acceptance: declaration, budgets, verdict, missing runs and DevTools overhead; every run's checks (value, budget, pass) and scalar peaks; then the failed predicates and invalid runs listed explicitly. Per-window sample vectors and post-close series dropped.

## Not retained

Per-window sample vectors and post-close series in both validations, sampled stacks and lower-ranked profile rows, full schedule samples (up to 57 MiB), packages and environments. Per-run inputs/after snapshots, exit codes, logs and pytest XML, raw/asset/install/cache/temp trees, candidate/baseline source copies and patches, and per-run reports already summarized above.
