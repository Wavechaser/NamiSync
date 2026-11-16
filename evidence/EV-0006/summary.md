# allocation: retained claim support

## Adequacy supplement — 2026-11-17

Historical whole-app aggregate recovered verbatim from `docs/PERFORMANCE.md` at
`cbf3f090a4af8468982202201d97048f37cc1252` (document SHA-256 `bc9599fb6ca7e204dd497c4eabc413c4e3b323d0ced795337fbb3402637a6671`).
The original `memory-probe-20261107` workspace was already absent at this correction;
its individual instrument/bundle manifests cannot be reauthenticated here. This is
the contemporaneous committed diagnostic summary, not a new independently
validated collection. The separately retained microbenchmark identities describe
that seam only. Renew measurement before using this historical comparison as an
acceptance claim. The delivered response-copy change is commit `cbf3f090a4af8468982202201d97048f37cc1252`.

From `ade6ba75`, the browser adopts private parsed native responses without
copying them again, freezes ordinary drain snapshots in place, and shares the
already frozen terminal snapshot across presentation retries. Mutable terminal
updates still receive a fresh copy per callback; shared completion-event data
still receives capture. BRIDGE owns these ownership requirements.

**Method.** `build/memory-probe-20261107/` contains private copies of the
`b6a4fefe` packaged app and full bundle manifests. Canonical product population
matches the current source except for the candidate's loose `bridge.js` asset;
only that asset differs between bundles. This is a diagnostic asset-overlay
comparison, not a rebuilt release. `probe.py` ran baseline, candidate, candidate,
baseline in fresh processes/profiles, with the retained 10,000 × 32 B source,
fresh targets under the repository's ignored build tree on F:, automatic
verification and 30-second unforced terminal/closed windows. Both source and
target are on F:, unlike the earlier F:/H: study. V8 sampling at 16 KiB includes
later-collected objects from Execute to terminal. Runtime: Edge 156.0.4314.58,
V8 15.6.12.10. Full tool/input hashes and source metadata accompany the receipts.

Only verified `baseline-sample-02`, `candidate-sample-01`,
`candidate-sample-02` and `baseline-sample-03` enter this comparison. Every run
had an exact mirror, unchanged source/bundle, exit 0 and an empty owned Job.
`baseline-sample-01` failed on sandbox loopback access and remains excluded.

| Observation (two fresh processes per arm) | Baseline | Candidate |
| --- | ---: | ---: |
| Sampled allocation during Execute, MiB | 533.06 / 490.95 | 434.50 / 427.50 |
| Mean sampled allocation, MiB | 512.00 | 431.00 |
| Execute + automatic verification, seconds | 84.269 / 83.255 | 85.300 / 85.309 |
| Renderer execution peak private MiB | 421.2 / 369.0 | 517.7 / 489.0 |
| Whole-app execution peak private MiB | 818.6 / 754.6 | 914.0 / 893.9 |
| Renderer final-15-second closed median private MiB | 322.3 / 299.2 | 395.5 / 393.8 |
| Whole-app final-15-second closed median private MiB | 757.8 / 715.9 | 821.6 / 818.8 |

Sampled allocation fell 15.82% by the two-run means. This small diagnostic
sample establishes neither a throughput gain nor lower process memory: both
peak and closed private memory were higher in the candidate. Allocation volume,
live heap and allocator/collector timing are different observations. No forced
GC occurred in these four runs. Reclamation probes are separate evidence.
All execution samples were complete; each run had one incomplete startup
sample. The sampling profiler was active during execution, so these process
figures do not establish unprofiled memory behavior. Clone-inclusive sampled
allocation averaged 138.53 MiB baseline and 0.031 MiB candidate; that attribution
is not interchangeable with the net total reduction. `allocation-comparison.json`
selects the verified runs explicitly and records both measures.

**Repeated use without allocation profiling.** `baseline-soak-01` and
`candidate-soak-01` reuse the existing 1,000 × 4 KiB fixture and 20-cycle
schedule: initial mirror, then ten changed files per cycle, explicit replacement
confirmation, automatic verification, 15-second closed windows and a final
120-second idle. All 40 mirrors and preserved-version counts passed, both
bundles stayed unchanged, and both processes exited 0 with empty Jobs.
`soak-comparison.json` records per-cycle windows. Medians across cycles 6–10
and 16–20 respectively:

| Observation | Baseline early → late | Candidate early → late |
| --- | ---: | ---: |
| Whole-app private MiB | 638.8 → 703.8 | 659.1 → 705.7 |
| Renderer private MiB | 239.9 → 306.1 | 274.1 → 304.4 |
| Browser-process handles | 1,266 → 1,265 | 1,263 → 1,265 |
| Renderer handles | 521 → 522 | 532 → 534 |
| Host private MiB | 122.9 → 126.4 | 122.3 → 124.5 |
| Host handles | 1,302 → 1,374 | 1,374 → 1,612 |

The final 120-second idle medians were 702.3/653.7 MiB whole-app and
306.1/256.5 MiB renderer, baseline/candidate (`soak-final.json`). Candidate
host handles dropped from 1,890 to 597 about 26 seconds into that idle and
stayed there; baseline finished at 1,369. Thus the candidate's higher late-cycle
host count did not persist. Final browser handles were 1,257 for both and
renderer handles were 522/524. Both ended with 55 GDI and 97 USER objects.
These observations show no additional browser handle accumulation or larger
late-cycle memory footprint in this bounded comparison. They do not fit a leak
slope or replace the earlier 100-cycle/long idle schedule; allocator and
collection timing remain visible in both arms.
