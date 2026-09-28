# Latest session — resumed executor performance round

2026-09-28, `milestone1-adelbert`, starting at `db05e31`. The user resumed and
explicitly authorized five follow-ups: document/remove the default Windows
anchor self-comparison; cheaper string-only cache eligibility; take leaf volume
from st_dev low 32 bits matching the held root serial, probing on mismatch;
one runtime admission per step; skip both real-path lookups when held. Prior
pause and pending-policy classifications are superseded for those mechanisms.
M1_PLAN owns scope; no additional filesystem-support or persistence change.

## Current outcome

Comments and CORE/EXECUTOR documentation clarify the default anchor comparison.
Its default observation echoes the admitted anchor, so comparison is not a
second freshness observation. Shared validation remains meaningful for injected
volume probes, including executor overrides. No bypass API or executable change
is introduced just to remove a setup-time comparison. Both Python ASTs match,
96 local links and diff checks pass; independent review approves in
`executor/independent-review-anchor-comparison-20260928.md` under the evidence root.

The next small executable outcome is string-only cache eligibility. A read-only
lane is mapping the last three outcomes against native/runtime owners and the
archived plan's access/effect-step boundaries. Preserve current held attributes,
unheld/custom fallback, descendant guards, settlement and dispatch. Do not treat
an entire plan operation as one step when callbacks, waits or effects divide it.

## Baseline and evidence

The preceding round passed 5,550 ordinary tests, four skips, 34 headed
exclusions; 12 imports, unchanged settlement 30 × three, guard scan 70/391/zero
missing admissions and all 67 qualified differential groups. Receipts remain
under `build/root-admission-optimization-20260928/`, including
`executor/independent-review-descendant-stat-20260928.md`.

Last three-sample executor median is 9.684 seconds / 0.403 MiB/s on 1,000 × 4 KiB
F:→G:. A 1 MiB/s result needs about 3.906 seconds; it remains a goal, not a gate.
`resume/executor-descendant-stat-*` retains timing, separate counts/profile,
source checks and scoped cleanup. PERFORMANCE owns methods and limits.

Retain the clean managed baseline checkout at
`C:\Users\Spectrum\.codex\worktrees\root-admission-baseline\NamiSync`, revision
`b8baf42df91e9aeed1402cd029c86ca9ae287b1b`, primary ignored raw/failed evidence,
the original F: source corpus and historical recovery refs `cfcc6ef`, `0a04921`,
`7eb8c19d`. Recovery changes were rebuilt, never merged as WIPs. No unrelated
branch/stash/remote changed. K: held-attribute/geometry observations pass; the
separate FileIdInfo compatibility defect remains deferred in BUGS.
