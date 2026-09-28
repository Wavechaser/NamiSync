# Latest session — proportional defense and executor run registration

2026-09-29, `milestone1-adelbert`, documentation only, after `23589bd` and
`8159905`.

## Delivered

- `103f3e48` adopted DEFENSE §2.5: demonstrably plausible triggers, proportional
  scale, the content/structure author split, the plan-fidelity bound, closed
  catastrophe backstops and guard-family dispositions (§2.5.3).
- This commit revises §2.5 so the backend executes what the user reviewed and
  refuses only when the actual effect would differ from the reviewed one;
  judging what users want belongs to the interface layers. It consolidates the
  delivered root-admission and incident rounds in M1_PLAN, registers the active
  executor simplification and throughput run with its declared oracle changes,
  records device ceilings in PERFORMANCE, and proposes directory-flush batching
  for M2.
- Review of `23589bd`: correct and equivalent on held roots; its gain is below
  run-to-run noise, and its error-precedence fallback is now optional under
  §2.5.1.

## Next

The implementer starts M1_PLAN's executor simplification run from this commit:
one admission per effect, one handle per copied file, planner-used drift facts
with the verifier walk trimmed, then direct large writes. The section grants
in-bound decision authority; its equivalence list and "needs a decision" items
bound it. M1-9 follows the run.

## Evidence and preservation

Device ceiling scripts and raw results: `build/executor-simplification-20260929/ceilings/`
(G: scratch removed; F: corpus only read). Earlier review probes:
`build/executor-review-20260928-30b0c2c8/`. Prior round evidence:
`build/root-admission-optimization-20260928/`, including the full-corpus
receipts `executor-runtime-full-23589bd3-20260929-000521-7fea29aa`. Preserve
`F:\NamiSyncExecutorBenchSource`, the `b8baf42d` baseline worktree, raw/failed
receipts and recovery refs `cfcc6ef`, `0a04921`, `7eb8c19d`.
