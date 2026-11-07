# Latest session — path, verification and retention investigation, 2026-11-07

## Outcome and scope

Investigated current product at `2ca0b291` without changing product or tests.
PERFORMANCE owns measurements and limits; M1_PLAN records completion and
M2_PROPOSAL records conditional verification-open discovery. No implementation,
GC policy, safety exception or performance budget is activated.

The next small COPY candidate is exact admitted root/anchor spelling reuse in
native `revalidate_root`, retaining every fresh held-handle attribute query.
Local validated component/prefix composition in `resolve` is a second candidate.
A 48-file native probe at depths 1/2/5 preserves exact outcomes and hashes;
pure-helper replay prices repeated root/anchor spelling at about 0.1 ms per
depth-two COPY, not an integrated saving. The earlier 25 root-hold queries/file
mixed owners: this COPY body has 19, plus two executor dispatch-entry guards.
No filesystem observation should be cached across accesses. Revisit native
path/fallback/root-mutation tests and the unchanged executor settlement gate
before implementation.

Recommend M2 discovery for bounded first-open lookahead inside automatic Verify.
Serial first-open latency does not prove Defender causality or parallel scaling.
Earlier locks/refusal observations need review; keep one ordered coordinator,
bounded owned handles/buffers and full worker settlement on controls. Overlapping
copy and Verify changes phase/checkpoint/recorder truth and requires a separate
workflow design. Grouped recording, parent flushes and small-file batching stay M2.

## Host and renderer findings

All checked task/session/plan/review/start-response/worker/subscription and bridge
response populations clear on Close; one bounded close receipt remains. At 10k,
50,400 FileStat, 10,100 PlanOperation and 10,000 IntegrityOutcome objects disappear
from the census. Traced live Python memory falls from 78.33 MiB at terminal to
26.26 MiB after Close, versus 24.59 at startup. Shared database/service/native
runtime state remains; process-private growth is not equivalent to live task data.

The traced Python-GC private-memory drop was confounded by instrumentation.
A separate untraced 10k run observes host private 163.28 MiB after Close,
165.01 after another passive idle window and 161.00 after Python GC. This
modest single-run change does not justify a broad host-GC/trim policy. Handle
counts vary between short runs and are not a new leak finding. The prior
long-run study remains applicable only to its recorded profiles.

Production renderer GC still runs before the Close response/frontend teardown.
A separate 1k diagnostic collects afterward under the existing backend-idle
reservation: embedder heap 20.26→4.93 MiB, JS heap already about 2.7 MiB,
renderer-private window medians 76.86→69.79 MiB. The latter is sequential and
includes idle time; the diagnostic latency field includes census work. Any
future post-teardown trigger must retain backend-idle exclusion and avoid
duplicate collection. Phase-transition GC, execution-time GC and heap caps
remain excluded.

## Verification and retained evidence

Four successful installed native runs pass exact mirrors, unchanged source
metadata/product, independent durable operation and verified-inventory audits,
clean terminal axes and normal exit with empty owned Jobs. All 303 product files
match the installed wheel/current source and 209 runtime files are hashed.
Runtime: Edge 157.0.4341.42 / V8 15.7.11.4 / Python 3.13.17. The initial sandbox
loopback startup failure is retained separately, with no target mutation and an
empty Job. No measuring-session process, profile or fixture was modified.

- `build/path-scope-20261107/`: native call trace, pure replay, matched producer
  hashes and source-backed candidate/gate report; its own disposable fixtures
  were removed after checks.
- `build/verify-scope-20261107/`: read-only source/ownership/evidence report.
- `build/host-retention-20261107/`: three frozen manifests, raw runs, owner/type
  census, allocation/native counters, durable audits, RESULTS.md and summary.json;
  fixtures/profiles intentionally retained. All owned apps are closed.
- `build/optimization-scope-20261107/`: integration and fresh independent review.

Documentation consistency/link/diff checks and independent review complete the
delivery. No broad product suite is claimed for unchanged executable behavior.
Earlier backend-idle GC is committed at `2ca0b291`; allocation and collection
diagnostics remain at `cbf3f090` / `2d86b1a0`.

The longstanding installed execution-review `exact-receipts` failure remains
unresolved. `fcb72b37` adds its trace; TESTS describes the sidecar and historical
paired evidence stays under `build/receipt-rate-20261106/`.
