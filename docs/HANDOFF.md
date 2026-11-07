# Latest session — shared executor root spelling, 2026-11-07

## Delivered changes

On base `323b5377`, native executor root revalidation reuses exact admitted
root/anchor spellings inside its active owning invocation. Reviewed volume and
anchor matching, fresh held-handle attribute queries, descendant checks and
operation ordering remain. Aliases and unavailable/foreign holds retain their
existing validation/admission routes. No path cache, observation fusion or
public contract change is added.

The same native method serves COPY, UPDATE, MOVE_UPDATE and non-byte operations;
no operation-specific optimization is needed. Product changes are confined to
`namisync/modules/executor/native.py`, with ten new native test cases.

Verification pipelining remains M2. No further post-task-close GC is requested.
Their scope and probe findings remain in PERFORMANCE and M2_PROPOSAL for future
revisits. Grouped recording, parent flushes and small-file batching remain M2.

## Verification and evidence

Evidence: `build/path-consolidation-20261107/` (drivers, hashes, raw receipts,
summary, findings and independent review). Baseline native tests pass 193;
candidate native tests pass 203, executor department 658, unchanged settlement
oracle 30 scenarios over three runs. Initial sandbox Temp setup errors are
retained; successful runs use the normal Windows Temp route.

Native before/after traces each verify 48 fresh 4 KiB copies at three depths,
exact SHA-256 mirrors, 48 published-evidence entries, source preservation,
settlement and owned-fixture
cleanup. COPY-body lexical conversions drop 30 to 10 with all instrumented
filesystem counts unchanged. Five paired fresh-process isolated guarded
revalidation samples have median-of-medians 15.20 to 2.09 microseconds. This is
not an integrated copy or headed throughput claim; PERFORMANCE records limits.

No application, measuring-session profile or study fixture was touched. No
branch/worktree was created. Task-owned probe fixtures are removed by their
exact-name drivers; ignored evidence remains. No release package was rebuilt.

## Immediate context

The previous Follow/receipt repair is committed as `1d1917c3` and `323b5377`;
its evidence remains in `build/verify-follow-20261107/`. The old installed
exact-receipts failure was a page-versus-full-result checker error and is resolved
there. This session does not rerun or supersede those interface gates.
