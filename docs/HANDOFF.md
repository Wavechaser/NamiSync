# Latest session handoff

## M1-7 P8: shared execution structure (2026-09-16)

Base `90d9469` on `codex/wip-20260914-1600-m1-7`. The user authorized
sharing validated execution structure through checkpoint materialization and
updated measurements. This round ends after one focused receipt comparison;
no full run, threshold change, amendment, integration or pruning.

### Change and preserved guarantees

Core `ExecutionSetCheckpoint` captures the existing construction-validated
structure and detached execution-authority baseline after validating the source.
Materialization shares that structure, copies the status, recording-reason and
publication-evidence dictionaries, checks the exact plan/selection/deselection
references, and validates the fresh continuation. The workflow uses this seam
for execute and verify checkpoints, including resume. Initial public
`ExecutionSet` construction still validates and builds the index.

Generic callback authority snapshots remain unchanged and nonvalidating;
dispatcher, service admission, commitment time and receipt placement are
unchanged. No new review-time index or legacy runtime representation was added.

One immutable operation index now survives while the checkpoint is paused and
is shared with reopened invocations. It disappears with its last owner.
Mutable overlays remain detached. ARCHITECTURE records both retained fields and
reachable mapping families; this is an extended index lifetime, not a claim of
zero memory cost. The plan-review memory fixture does not measure paused
execution retention.

### Verification and measurement

Focused checkpoint/bridge-resume/post-execution corpus: 259 passed (7.39 s).
The tests cover both phases, sharing without constructor/index reconstruction,
mutable isolation, malformed or mismatched state and public validation.
Independent source/retention review and 12 import contracts pass.
Ordinary suite: 5,157 passed, 5 skipped / 30 deselected (267.91 s).
Fresh installed Plan GUI: 1 passed / 2 deselected (59.14 s).
Receipt readiness passed, then five fresh measurement processes completed
30 warm samples without retry. **P95 is 72.0 ms; maximum is 72.9 ms** against
the unchanged **100/250 ms** limits: both pass. The previous result was
121.9/122.7 ms, so p95 fell 49.9 ms (40.9%). Samples range from 43.5 to 72.9 ms;
per-child maxima are 58.2, 66.6, 72.0, 72.0 and 72.9 ms. These are focused
diagnostic results, not a fresh full M1-7 acceptance run. Stop after this round.
Independent `comparison/evidence-audit.json` passes: six unique child/process/
token identities, all raw receipt/invocation/log hashes, 42 declared source files,
38 installed/wheel members, 14 runtime files and the supplemental core execution
source/installed/wheel triplet. The audit independently recomputes the statistics.

### Evidence and operational context

Evidence root: `build/m1-7/evidence/p8-structure-20260916/`. It contains
focused verification, check scripts and the reviewed receipt-only driver.
The driver retains fresh authority and incremental child receipts under
`comparison/`, including a supplemental source/installed/wheel-member hash
triplet for `core/execution.py`, absent from the historical contract's file list.
Protected contracts and historical evidence were not edited.

The immediate comparison baseline is P7 p95/max **121.9/122.7 ms**, against
unchanged **100/250 ms** limits; raw evidence remains under
`build/m1-7/evidence/p7-receipt-20260916/`. Earlier P6 sorts and review memory
passed their focused checks, but those results are not a fresh full M1-7 run.
Keep `cf5a00b`, `30d35f3`, `28c7b44`, `a479e58` and `90d9469` unchanged.
`milestone1` remains `40ca76f`; M1-7 stays unmerged on the recovery branch.
