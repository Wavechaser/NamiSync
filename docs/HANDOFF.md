# Latest session handoff

## M1-7 P7: digest reuse and focused receipt comparison (2026-09-16)

Base `a479e58` on `codex/wip-20260914-1600-m1-7`. The user authorized a
short admission timing breakdown, then digest reuse first if warranted and
updated focused measurements. No early receipt, dispatcher redesign, threshold
change, full measurement round, amendment, merge or branch pruning.

### Attribution and correction

The single installed headed diagnostic used the existing 100,000-operation
receipt fixture: one warmup and six paired observations. Median digest time was
51.654 ms; two `ExecutionSet.__post_init__` calls together took 76.292 ms;
remaining service admission took 10.320 ms. Service total was 140.381 ms and
browser receipt 142.700 ms. These last two observations have separate timing
domains; they do not establish a bridge-only duration. Phase medians need not
sum. An earlier component-only probe (one warmup/five observations) measured
39.503 ms digest and 28.660 ms initial construction; it omitted real admission
and checkpoint materialization and is a separate diagnostic distribution.

The workflow-derived selection now retains one canonical 32-byte digest.
Preview, review and commitment consume it through the same exact-plan and
deselection authority. Commitment still creates its timestamp at admission;
revision, destructive acknowledgment and public constructor checks remain.
The receipt still follows actual admission, attachment and publication.
The benchmark's normalization/digest helper consumes the prepared value,
preserving one digest computation and its named endpoint. Protected contracts
and historical evidence remain unchanged.

One bytes object plus its field slot is added to each existing decision; no
sorted/serialized digest input or extra operation index is retained. Mutation,
artifact replacement and retirement retain their existing decision lifecycle.
Focused tests cover canonical equivalence, no repeat hashing, fresh timestamps,
identity guards and mutation/replacement. No core or dispatcher source changed.

### Verification and measurements

Focused workflow/service checks: 82 passed. Scale-contract check: 1 passed.
Import contracts: 12 kept, zero broken. Independent source review passed.
Ordinary suite: 5,153 passed, 5 skipped / 30 deselected (262.45 s).
Fresh installed Plan GUI: 1 passed / 2 deselected (48.65 s).
Receipt readiness passed, followed by five fresh measurement processes and
30 warm samples. Receipt p95 is **121.9 ms** (limit 100 ms); maximum is
**122.7 ms** (limit 250 ms). The p95 still fails; maximum passes. The previous
focused round was 170/175.4 ms, so p95 improved 48.1 ms (28.3%).
Samples range from 79.8 to 122.7 ms; per-child maxima are 112.5, 122.7, 104.4,
121.9 and 114.9 ms. This is a diagnostic comparison, not full M1-7 acceptance.
The run completed without a retry or functional/harness blocker. Stop here
before another optimization or measurement round; criteria remain unchanged.
Independent evidence audit passed: six unique child/process/token identities,
30 samples, all receipt/invocation/log hashes, 42 source files, 38 installed/wheel
members and 14 runtime roles match the frozen authority. See
`comparison/evidence-audit.json`; this audit does not promote the comparison to
terminal acceptance.

### Evidence and next boundary

Evidence root: `build/m1-7/evidence/p7-receipt-20260916/`. The baseline
`breakdown.json` and `headed_breakdown.json` retain raw samples and provenance;
the latter freezes source/installed hashes, loaded module paths, interpreters
and diagnostic scripts before product edits. `receipt_comparison.py` is the
reviewed one-shot driver for one readiness child and five measurement children,
six samples each, against the unchanged 100/250 ms p95/max limits. It preserves
fresh authority and incremental child receipts under `comparison/`.

The second constructor call comes from `ExecutionCheckpoint.materialize`.
With receipt p95 still over budget, the next candidate is sharing the already
validated immutable structure through checkpoint materialization while keeping
fresh mutable state and admission checks. That needs a separate reviewed change;
it was not implemented in P7. Preparing another review-time index is unnecessary
for that narrower candidate. No broad dispatcher change is justified here.

Prior focused results remain in `build/m1-7/evidence/p6-resume-20260916/`:
all six sorts and memory passed; receipt p95/max were 170/175.4 ms.
Keep `cf5a00b`, `30d35f3`, `28c7b44` and `a479e58` unchanged.
`milestone1` remains `40ca76f`; M1-7 stays unmerged on the recovery branch.
