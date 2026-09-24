# Latest session — post-R2 control edges and probe safety

Base: reviewed R2 `c974447` after observer correction `b1f5a07`.
Candidate: `F:/GitHubRepositories/NamiSync/build/m1-8-r0`, branch
`codex/m1-8-control-edges`. The accepted `codex/m1-8-r2` ref remains intact.
The user authorized the two deferred product edge fixes in a separate commit,
and requested durable probe safeguards instead of routine memory watching.
M1_PLAN's Post-R2 correction register owns PS-1 and CE-1/2.

## Scope and current work

PS-1 is complete: bound the ordinary frontend Node probes through the existing
prelaunch Job launcher, keep file-backed diagnostics bounded, and make Plan/task
fake DOM inspection concise without weakening identity assertions. Preserve
native launcher defaults and frozen historical/quantitative instruments.

CE-1/2 then share one product commit: disable execution controls after updates
stop, and retain task/session-owned control feedback across review replacement.
Preserve native execution truth, reject obsolete replies and prevent duplicate
controls. No new recovery UI, reattach protocol or backend behavior. Task Close
can remain pending without terminal delivery, so it must not be promised as a
working reconnect path; app close can request cancellation without promising
completed cancellation or resumability.

PS-1 passed its populated-graph, allocation/output/timeout and original-probe
controls, 5,405 ordinary tests (five skips), 12 import contracts and independent
review. The product lane remains pending. Evidence belongs in
`build/control-edges-20260924/`. Tests use automatic containment; inspect memory
only for failures or a declared resource gate, not through live babysitting.
Product edits invalidate current-source reuse of U run-03: preserve it and run
fresh fixed-profile U acceptance before the product correction commit.

## Baseline and preserved evidence

R2 passed 101 focused U/P2 tests, 5,401 ordinary tests (five skips), 13 native
paths and 12 import contracts. Fresh run-03 completed all 78 attempts and passed
independent raw, staged and clean-HEAD validation. Its 40 cold/150 warm samples
had worst values 20.9 ms cold maximum, 64.4 ms warm p95 and 64.9 ms warm maximum.
`build/r2-20260924/delivery-03.json` and `review-03/REPORT.md` bind the delivery.
Prior failed collections and diagnostics remain preserved, never acceptance.

Original checkout remains `codex/m1-8-r0` at P2 `4bbf943`; milestone1 remains
`055325b`. Protected stash `93414b7...`, unrelated `af02913`, recovery branch
`codex/wip-20260924-1233-r2` at `b4ea0eb`, worktrees and evidence remain intact.
R3 integration, push, PR, cleanup, filter/Search and the reduction study remain
excluded. Stop after the authorized corrections.
