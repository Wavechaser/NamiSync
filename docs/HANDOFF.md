# Latest session — root admission replanned around held roots

2026-09-28, milestone1-adelbert. The user stepped back from the nine-row RO
register, which had never reached implementation, because its up-front
specification kept stranding the work. M1_PLAN now carries a one-page,
results-oriented plan. The old register stays in Git history at `c05eea25`. This
commit is documentation only; implementation starts when the user authorizes it.

Decisions in the new plan:
- Target above 1 MiB/s for 1,000 × 4 KiB F:→G: execution, as a goal, not a gate.
- Hold each admitted root per invocation, using directory access without delete
  sharing, instead of re-admitting it on every access. "In use" failures for
  rename, move and Safely Remove are acceptable. The point-of-use contract
  wording changes when the hold ships.
- Keep the per-access fallback for UNC, mapped or unholdable roots, and still
  cut `GetVolumePathNameW` and related calls there and in each invocation's
  single admission.
- Equivalence against the baseline uses must-match / may-differ /
  needs-decision bands. One probe-only oracle re-pin is allowed.
- Commits are atomic with no size cap. There is no M1-9/M1-10 coupling.
- Oracle v2, root continuity, EW-5/EW-6 and the absolute swap-sweep criteria are
  dropped.

Hold witness (read-only scratch probe, cleaned up): on NTFS C: and exFAT K:, a
held root opened with `FILE_LIST_DIRECTORY` and no `FILE_SHARE_DELETE` blocks
renaming the root (error 32) and its ancestors (error 5), while changes inside the
root stay allowed. An attribute-only handle does not block renaming the root. SMB
is unwitnessed and uses the fallback. Root deletion still needs a witness when
the hold is implemented.

Reusable evidence under `build/root-admission-optimization-20260928/`:
- `baseline/`: 5,410 ordinary passes, 12 import contracts, oracle 30 × 3 at
  `b8baf42d`.
- `ro0a/`: v1 capture and the 70-row / 391-call guard scan with zero missing
  guards.
- `ro0b/`: the root-replacement probe and the 12-case identity-weak probe
  (identity-bearing cases refused; four identity-less DELETE/TRASH cases acted on
  the replacement). Both are recorded in the plan as pre-existing findings
  outside this work.

The isolated baseline worktree stays at
C:\Users\Spectrum\.codex\worktrees\ro-baseline\NamiSync (`b8baf42d`, own Python
3.13.14 venv); run it with its own cwd. It serves the equivalence differential.

Recovery branch `codex/wip-20260928-0117-root-admission` holds an untested
partial oracle-v2 tool edit that is now superseded. Never merge or cherry-pick
it; prune it once the user agrees nothing in it is needed. DOC-2, stashes and
other refs are untouched. No push was made.

Next action: user authorization, then step 1 (core hold primitive, witnesses and
admission call reductions), measured against the target.
