# Latest session — control-edge corrections complete

Candidate: `F:/GitHubRepositories/NamiSync/build/m1-8-r0`, branch
`codex/m1-8-control-edges`, based on accepted R2 `c974447`.
M1_PLAN's Post-R2 register owns PS-1 and CE-1/2. R3 is not started.

## Changes

- PS-1 commit `96a0212` automatically bounds ordinary frontend Node jobs,
  diagnostic reads and fake-DOM failure inspection while preserving assertion
  truth. Native launcher defaults and frozen historical instruments stay intact.
  Routine tests need no memory watcher; investigate failures or named resource gates.
- CE-1/2 share the following product commit, identified by
  `build/control-edges-20260924/delivery-01.json`: retain task/session-owned
  control attempts across review replacement, prevent duplicate dispatch and
  reject obsolete replies. Lost active drains disable execution controls even
  when refusal arrives before review loading completes. Terminal cleanup keeps
  its prior guidance; no backend commands or execution policy changed.

Lost updates do not prove execution stopped. Closing NamiSync requests
cancellation without promising completion or reconnect. Task Close may remain
pending without terminal delivery; no reattach or new recovery UI was added.

## Verification and evidence

Three focused production/native checks, 33 fresh installed GUI tests, 5,405
ordinary tests (five skips), 12 import contracts and 76 checker controls against
the promoted U artifacts passed. Independent source
and raw-evidence review is in `build/control-edges-20260924/review/CE-review.md`;
reproductions and focused commands are in `builder/REPORT.md` under that root.

Fresh U `run-01/` completed all 78 attempts once (13 readiness, 65 measurement;
40 cold and 150 warm samples). Full raw/workspace validation passed: worst
cold maximum 10.2 ms, warm p95 68.8 ms, warm maximum 70.4 ms, within unchanged
budgets. The three active U JSON artifacts bind this corrected product.
`delivery-01.json` is written only after staged and clean-HEAD validation;
its commit/tree/hash identities are the final closure record.

## Preserved state and next scope

Accepted predecessor evidence remains under `build/r2-20260924/`, including
run-03 and `delivery-03.json`; failed runs 01/02 are preserved, never acceptance.
Original checkout remains clean on `codex/m1-8-r0` at P2 `4bbf943`; milestone1
remains `055325b`. Accepted `codex/m1-8-r2` remains `c974447`; recovery
`codex/wip-20260924-1233-r2` remains `b4ea0eb`. Protected stash `93414b7...`,
unrelated `af02913`, worktrees and evidence are untouched.

Stop after these corrections. R3 integration, push, PR, cleanup, filter/Search
and the M1-7 reduction remain excluded. Review and authorize R3 separately.
