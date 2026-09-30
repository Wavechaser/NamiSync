# Latest session — consolidation and threshold probing complete

2026-09-30, `milestone1-adelbert`. Consolidation is committed as `878f15e`.
The user explicitly approved single-path root admission and returning saved
changes to this branch, then clarified that measurements mean the direct-write
threshold sweep. Production direct-write refactoring has not started.

## Delivered

- `8b2b00e`: refined directive, committed before implementation.
- `d43f832`: executor/recorder own-effect version recognition.
- `6157226`: admitted-root path composition.
- `878f15e`: remove method-identity dispatch, preserve native guards/fallback,
  migrate override tests to primitive controls. Fresh independent review passed.

Result 7 gates: 331 native/runtime and 5,699 ordinary tests passed, four existing
skips, 34 deselected; imports 12, unchanged oracle 30x3, guard scan 70 rows /
391 effects / zero missing, fixed differential 67 groups / zero differences.
The 12-test reduction retires redundant override dispatch variants, preserving
no-effect/source-swap checks. Failed migration controls remain in evidence.
All 25 consolidation executions/readbacks passed with zero reservations, stable
dependencies and owned cleanup; predecessor ranges overlap.
Evidence: build/executor-simplification-20260929/differential/result7-* and
measurements/result7-6157226f-20260930-170339-3d6968b5*.

## Threshold result and limits

After result 7 review/commit, the standalone paired 2/4/8/16/32 MiB sweep on
G/H/E/J/L from F, with G6/L24 refinements, supports candidate thresholds of
G: 6 MiB and E: 2 MiB (the sweep floor). Keep H/J/L buffered: the benefit was
not sustained under the predeclared 5-of-6 pairs / 5% median saving criterion.
These recommendations describe the measured physical devices and serial,
warm-source QD1 copying. They do not establish universal device classes or
integrated pipeline performance. PERFORMANCE owns the method, tables, limits
and receipts; M1_PLAN records completion and keeps result 8 implementation pending.

All 336 timed copies and 16 nonaligned tail witnesses passed exact unbuffered
readback, source/dependency hashes and exact cleanup. Pilot samples are retained
separately from the primary decision. No sample discarded or favorable rerun.
Evidence under build/executor-simplification-20260929/ceilings/:
- threshold-baeeeab32bd6495ca4a5f75799619bbe (pilot).
- threshold-d230a636d6fc4f38b79e20d003c59b93 (primary).
- threshold-0dfc0f6a45f1463a9ea6cf4feacd4fad (G6).
- threshold-09c326775f964b919f8e4eccac9ed1cf (L24).
- direct_write_threshold-reviewed-878f15e.py (immutable measured helper).
- threshold-observations-878f15e.json and summarize_threshold.py (derivation).

## Recovery accounting and next work

Recovery 9f01bfd9 saved core planning, executor runtime, two tests and delivery
docs. Useful source/tests were rebuilt and verified in d43f832; temporary
M1/HANDOFF prose is superseded by the accepted record. Recovery 259aee0 saved
native admission and two delivery docs; all three were restored as uncommitted
changes on milestone1-adelbert and rebuilt into 878f15e. Neither WIP was merged
or cherry-picked. Both fully accounted task recovery refs were removed at
closeout. No task worktree was created. The unrelated b8baf42d
worktree, original F source and all historical/failed evidence remain intact.

Next: review the measured candidates when designing result 8. Revalidate any
changed production buffer/concurrency/finishing design; retain its safety and
acceptance contract. No production writer, pipeline, device classifier or
shipping threshold changed in this session. Native tests use actual-user and
default pytest temp. Documentation link/diff checks and fresh independent raw
evidence review passed; no product dependencies changed after acceptance.
