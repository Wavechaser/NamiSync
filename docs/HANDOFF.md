# Latest session — Plan Follow allocation, 2026-11-08

## Outcome and scope

Base is `b5b6071b`. The user authorizes reducing the repeated Plan-window DOM
construction responsible for higher execution peaks after verification Follow
began tracking settled items. Keep that target behavior, and keep GC policy.

Plan Follow now uses a matching operation already in its current session/view/
highlight window without another Follow anchor/window read. Compatible rows in
active committed overlapping windows retain DOM and listeners, with current row
bindings and changed execution cells. Static changes rebuild affected rows.
Only the current bounded window is retained, without an off-window row cache.

Review identified two navigation-custody gaps in the new local landing path.
The common visible-page guard blocks hidden Settings work; local Plan jumps
retire exact older viewport requests before publishing, preserving highlight
and selection ownership. `navigation-review.md` records the mechanism review.
The obsolete refresh-only marker was removed so actual Follow/viewport windows
can use overlap reuse. No backend/protocol or collector changes are included.

## Verification and evidence

Functional evidence is in `build/follow-allocation-20261108/`. Counted renderer
replays create 98/770/3,074 elements before versus 26/26/26 after for a one-row
shift and one changed execution row at widths 8/64/256. Identity, handler freshness,
no off-window cache and static-change fallback witnesses accompany those counts.
The initial 2,261-case interface pass predates the final navigation-custody
correction. The final 2,261-case interface run and four installed task-shell/
execution-review cases pass on the frozen correction. The final headed command
explicitly clears default addopts. Source/test hashes are recorded in
`identity.json`.

Native comparison evidence is in `build/follow-memory-20261108/`. Four isolated
10k × 32 B source-app runs use baseline/candidate then candidate/baseline order,
matching producer/runtime and normal GC. A fixed two-second terminal pause
avoids mixing the previously observed immediate-close race into this comparison.
All four runs pass exact mirrors, source preservation, durable operation/Verify
audits and normal empty-Job exit. Sampled DOM peaks fall from 138–160k to 64–68k,
embedder heap from 415–484 to 212–221 MiB, and renderer private peaks from
976–1,080 to 776–779 MiB. PERFORMANCE records exact ranges, methods and limits.
These are diagnostics, not release acceptance or a 100k/long-soak result.

## Immediate operational context

Existing measuring-session processes, profiles and fixtures are untouched.
New native probe fixtures/profiles and ignored evidence belong to this task and
remain registered under its evidence root. No task branch/worktree was created.

The prior 17-run rebuilt-package study and source bisection remain documented
in PERFORMANCE and under `build/resource-study-20261108/` and
`build/peak-bisect-20261108/`. Slow overnight exit was attributed to environment;
two early-close stalls remain unexplained and are outside this change. Prior
study fixtures remain retained and must not be removed with this task's files.
Verification pipelining, grouped recording and small-file batching remain M2.
No further post-task-close GC is added.
