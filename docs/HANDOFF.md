# Latest session — own-effect version recognition

2026-09-30, `milestone1-adelbert`, result-5 candidate based on `8b2b00e`.
The explicit user authorization resolved the recorder approval block. Active
scope remains results 5–7, with small atomic commits and measurements; result 8
and direct writes are excluded.

## Delivered candidate

Core version recognition now serves executor post-effect/recovery checks and
pure MOVE/RECASE recording. Plan predicates reuse it with planner metadata facts.
Readonly-restoration completion and SQL row concurrency remain strict; actual
resulting metadata is recorded. Five native ARCHIVE cases and real version-change
controls cover the fix. Source/test/component docs are frozen and independently
reviewed; delivery docs record the final evidence before the atomic commit.

Final verification: 27 focused checks; 5,714 ordinary tests passed, four existing
capability skips, 34 deselected. The full ordinary suite covers the core,
executor and database departments. Imports retain all 12 contracts. The unchanged
settlement oracle passes 30 scenarios x three runs, admission scan reports
70 rows/391 effects/zero missing admissions, and the fixed differential has
67 groups with zero differences. Earlier receipts are retained but superseded
by final predicates; the initial ordinary run overlapped the composition edit
and is not acceptance for final bytes.

Evidence root: `build/executor-simplification-20260929/`. Final logs use
`differential/result5-final-*`; differential capture is
`runs/candidate-result5-final-ee4cb82faa6f427baec078c2bb6e1c36/` under that directory.
Five-band prefix: `measurements/result5-8b2b00e4-20260930-130559-e544fed6`.
All 25 executions/readbacks passed with zero reservations, unchanged source and
dependency manifests and owned-target cleanup. Medians: 3.222 / 1.685 / 0.341 /
0.296 / 1.981 s. All predecessor ranges overlap; no throughput lift is claimed.
PERFORMANCE owns the full table and limits.

## Next work and recovery accounting

Commit the verified coherent result 5, then results 6–7 follow. Result 6 stays
in native path composition and its tests; no conversion-time filesystem query,
weakened descendant guard or fallback admission is intended. Result 7 removes
method-identity dispatch and migrates custom override controls to primitives.
Revalidate read-only design against the integrated result 5 before edits.

`8b2b00e` committed the directive. `9f01bfd9` remains on
`codex/wip-20260930-1246-executor-version` as recovery only. Its six saved paths
were restored as uncommitted changes, reviewed and corrected; no WIP merge or
cherry-pick occurred. Keep that ref until final integrated accounting, then
remove it. No task worktree was created. Original F: source, old evidence and
unrelated `b8baf42d` worktree remain protected. The saved fixed starting baseline
is available without restoring its archived checkout. Native gates use actual
user/default pytest temp. No direct-write implementation or sweep has started.
