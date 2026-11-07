# Latest session — execution allocation and pending GC probes, 2026-11-07

## Allocation outcome

From `ade6ba75`, remove redundant copies of freshly parsed native direct and
observed responses, freeze ordinary snapshots in place, and share the frozen
terminal snapshot across retries. Keep terminal update copies per callback,
initial terminal capture, shared completion-event capture, validation and
native receipt/release ordering. BRIDGE documents ownership; the interactive
test exercises installed pywebview's actual return parser and backing mutation.

Verification: 166 focused tests, 2,224 ordinary interface tests and six installed
native transport cases passed. An earlier department run produced setup errors
without traceback and was interrupted; the clean fail-fast rerun passed. Its
partial log is retained, not treated as passing evidence. Independent review
checked source/test ownership, diagnostic methods and raw measurement receipts.

Four matched 10k execution samples in B,C,C,B order show 15.82% lower mean
sampled allocation (512.00 → 431.00 MiB). Profiled private memory was higher
in the candidate and throughput did not improve. Two unprofiled 20-cycle soaks
passed all 40 mirrors/preserved-version checks and normal closes, with comparable
late browser memory/handle counts. This is a bounded regression observation,
not a replacement for the previous full stability schedule. PERFORMANCE holds
the tables, provenance and caveats, including the post-close memory tradeoff.

Evidence:

- `build/allocation-20261107/`: frozen microbench inputs/hashes, six Node
  receipts, builder review notes, interrupted department log and passing gates.
- `build/memory-probe-20261107/`: private baseline/candidate bundles and
  manifests, four verified sample runs, two verified soaks, comparison JSON,
  fixtures registry and raw profiles/resources. `baseline-sample-01` failed on
  sandbox loopback access and is excluded; later native launches used escalation.
- Original full-study evidence remains `build/resource-study-20261106c/`;
  PERFORMANCE retains its baseline conclusions. No original package or fixture
  was modified. Test targets are under the task-owned ignored build tree.

## Immediate next work

After committing this allocation outcome, run the prepared candidate GC probes
at 10k and 100k, then the separate native Low/Normal target probe. These are
diagnostic experiments only; do not introduce a production GC policy. Preserve
unforced memory windows, distinguish JS heap/private bytes/working set, verify
normal restoration and a new Plan, and report responsiveness plus exact mirrors
and normal process closure. Driver details are in the evidence README and M1_PLAN.
The original successful allocation driver is frozen as `probe_allocation.py`;
GC/Low progress logging has separate producer hashes.

Commit updated findings and HANDOFF promptly at completion to avoid collision
with another session's context update. No other session's processes were changed.
The longstanding installed execution-review `exact-receipts` failure remains
unresolved; `fcb72b37` added a failure trace. TESTS describes preserving that
sidecar. Existing paired failure evidence remains `build/receipt-rate-20261106/`.
Grouped ledger commits/parent flushes and small-file batching remain M2 work.
