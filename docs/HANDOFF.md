# Latest session — M1-8 closure

RC-1 is `3ea4e6b`: Retry updates restores observation of the same retained
task/session and lets pending Close settle. Uncertain Close keeps its fence
and exact retry. The correction is separate from R3 documentation/integration.

The authoritative final integration receipt is
`build/m1-8-archive-20260924/integration.json` in the main checkout. It binds the
reviewed candidate, non-squash `milestone1` merge, exact tree and postmerge
source/wheel/install/U-artifact validation. M1_PLAN A6 defines closure: matching
merge/tree plus PASS means M1-8 is complete; an absent receipt means integration
is still open. This avoids claiming completion before the merge succeeds.

Verification: 5405 ordinary passes/five skips, all 33 installed GUI obligations,
12 import contracts, 60 focused checks and 76 artifact controls. Fresh fixed U
acceptance completed all 78 attempts: cold maximum 20.3 ms, warm p95 72.0 ms,
warm maximum 73.3 ms. Full 265-input/262-package-file identity, staged and
clean-HEAD validation passed. The nine initial headed fixture failures and
their passing corrections remain documented; failed R2 runs stay failed.

After the verified merge, cleanup moves the candidate's `build/` intact under
`build/m1-8-archive-20260924/evidence/`. Its `recovery-close-20260924/` directory
contains delivery-01, RC/R3 reviews, raw run-01, captures and accounting.
`evidence-move.json` and `cleanup.json` in the archive record the actual
preservation and removal outcome; absent receipts mean cleanup is not complete.
The seven historical recovery refs remain
in a verified bundle, and the detached worktree's four dirty files are archived.
Cleanup is limited to accounted M1-8 refs/worktrees; unrelated GUI refs and all five
stashes remain. Historical absolute paths are provenance; the archive is their
relocation, not a rewritten acceptance artifact.

Stop after M1-8. Filter/Search, theme changes, M1-7 reduction-study resumption,
M1-9, push and PR remain excluded. Future M1 and release obligations remain
in M1_PLAN. Automatic probe bounds and safe fake-DOM assertions remain the
resource safeguards; no routine memory watcher is required.
