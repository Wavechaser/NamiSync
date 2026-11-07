# Latest session — allocation reduction and GC findings, 2026-11-07

## Delivered

Allocation change committed as `cbf3f090`. The bridge adopts private parsed
responses without redundant copies, freezes ordinary snapshots in place, and
shares the frozen terminal snapshot across retries. Terminal update copies,
shared completion-event capture, validation and native custody/release ordering
remain intact. No production GC timer or memory-target policy was added.

Four matched 10k executions sampled 15.82% less allocation (512.00 → 431.00 MiB
mean, two processes per arm). Profiled private memory was higher in the candidate;
throughput did not improve. Unprofiled 20-cycle baseline/candidate runs passed all
40 mirror/preservation checks and normal closes, with comparable late browser
memory/handles. These bounded observations do not replace the earlier full
stability schedule.

GC diagnostics on the optimized candidate:

| Open task, after unforced idle → forced GC | 10k files | 100k files |
| --- | ---: | ---: |
| JS heap, MiB | 214.87 → 3.08 | 718.12 → 4.55 |
| Renderer private, MiB | 353.20 → 95.45 | 1,141.58 → 131.31 |
| CDP collection round trip | 38.03 ms | 83.06 ms |

The command durations are not isolated GC pause measurements. Closed-task GC
measurements follow prior open-task GC. The 100k run completed execution and
automatic verification in 847.807 seconds; source preparation and independent
post-run checks are outside that timing.

A separate frozen source-host experiment verified native Normal → Low → Normal.
Low left JS heap around 202 MiB and renderer private around 337 MiB, while the
OS-reported renderer working set fell to zero in all 15 complete tail samples.
GPU private fell about 76 MiB. This is consistent with residency trimming,
without substantial net JS-heap reduction or proof of disk paging. Normal
restoration and a second no-op Plan passed. No frame gap exceeded 50 ms in the
five-second Low/restore observations; later response checks took about 1–9 ms.
These are not latency
guarantees. PERFORMANCE records exact windows, runtime differences and limits.

## Verification and evidence

- 166 focused tests, 2,224 ordinary interface tests and six installed native
  transport cases passed. Independent adversarial reviews covered allocation
  ownership, tests, measurement producers, raw receipts and final reporting.
- Both native GC runs and the corrected Low run passed exact mirrors,
  unchanged source/bundle checks and normal exit with empty owned Jobs. Every
  reported resource window is complete. All owned apps are closed.
- `build/allocation-20261107/` retains frozen microbench inputs/hashes, six
  Node receipts and test evidence. An earlier department run with setup errors
  was interrupted without traceback; the clean fail-fast rerun passed.
- `build/memory-probe-20261107/` retains private bundles, fixtures, manifests,
  raw runs and `allocation-comparison.json`, `soak-comparison.json`,
  `soak-final.json` and `gc-report.json`. `candidate-commit-binding.json`
  binds the measured asset to the commit. Drivers/versions are frozen separately.
- Excluded measurements remain preserved: `baseline-sample-01` was denied
  sandbox loopback access; the first Low pilot passed behavior/closure but
  misclassified its Python redirector, invalidating aggregate completeness.
  The corrected diagnostic wrapper changed no product or common collector.
- Original study evidence remains `build/resource-study-20261106c/`. Its
  package and fixtures were untouched. New targets/profile copies are registered
  under this session's ignored build tree; no unrelated processes were changed.

## Operational context

The requested optimization and probing are complete. A future inactive-window
memory policy needs an activity/restore design and pressure/resume evidence;
Low is not a promised JS cleanup mechanism. Repeated 100k use and behavior under
system memory pressure remain unmeasured. No such follow-up is scheduled here.

The findings and HANDOFF travel together in this documentation commit. The
longstanding installed execution-review `exact-receipts` failure remains unresolved;
`fcb72b37` added its failure trace. TESTS describes preserving that sidecar;
paired old failures remain in `build/receipt-rate-20261106/`. Grouped recording,
parent flushes and small-file batching remain M2 work.
