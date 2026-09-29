# Latest session — root-admission WIP cleanup

2026-09-29, `milestone1-adelbert`, starting clean at `b1b58476`.

## Cleanup

Accounted for the sole unique commit on each of the four WIP branches, then
pruned their local refs. None was checked out; no recovery commit was merged.

- `c833bb99`: partial oracle-v2 tool draft retired by `3c8b4b41`; finding and
  probe evidence retained. No product, test or baseline change was in this WIP.
- `cfcc6ef`: core hold code/tests/docs rebuilt in `6536c041`, replacing identity
  comparison with strict final-path confirmation; `8cdd669` added live attributes.
- `0a04921`: docs-only blocked executor proposal superseded by `90b57646`.
- `7eb8c19d`: preflight code/tests/docs rebuilt in `4263b12` with the held-attribute
  correction and its native refusal regressions.

Exact branch names, tips, unique histories, changed-path populations and
successor ancestry checks are retained in
`build/root-admission-optimization-20260928/resume/wip_cleanup_20260929_accounting.json`.
The neighboring verified `.bundle` preserves all four recovery commits; its
prerequisite commits remain in the integration branch. Product/tests were not
changed, so no product test rerun was needed. Documentation links/diff and an
independent accounting review cover this cleanup.

## Next work remains unchanged

`b1b58476` registered M1_PLAN's executor simplification run after `103f3e48`
adopted proportional defense. Follow that active register: one admission per
effect, one handle per copied file, planner-used drift facts with the verifier
walk trimmed, then direct large writes. Its equivalence list, authorized oracle
changes and decision boundaries remain binding. This cleanup does not start
implementation or change the run's scope; M1-9 follows it.

## Preservation

Keep `F:\NamiSyncExecutorBenchSource`, the detached `b8baf42d` baseline worktree,
raw/failed root-admission and full-corpus receipts, review probes and device
ceiling evidence. No other branches, worktrees, stashes or remotes were changed.
