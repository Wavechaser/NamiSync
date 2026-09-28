# Latest session — executor performance round

2026-09-28, `milestone1-adelbert`, resumed from `db05e31`. M1_PLAN owns scope.

## Delivered

- `d88219d`: document the default anchor self-comparison; preserve meaningful
  injected-probe validation without adding a bypass API.
- `acdaefa`: string-only cache eligibility, median 7.756 seconds / 0.504 MiB/s.
- `0c8d304`: stat-derived leaf volume on matching held serial, median 5.383
  seconds / 0.726 MiB/s; fresh probe fallback and custom dispatch remain.
- Current held-resolution outcome: default confirmed holds skip both physical
  resolutions, preserving live held attributes, descendant no-follow checks,
  must-exist policy and custom/unheld fallback. Median 3.387 seconds / 1.153
  MiB/s (3.370–3.388) exceeds the non-gating goal on 1,000 × 4 KiB F:→G:.

Separate profiles confirm physical resolutions 26,000→zero, stat calls unchanged
at 23,006 and runtime root revalidation still 27,000. Project-native counts stay
at two anchor/two volume queries, 2,002 opens/closes, two final-path queries and
37,998 handle-information queries. All copies/readbacks, source rechecks and
manifest-scoped target cleanup pass; instrumentation is not timing authority.

## Verification and review

Latest outcome: 464 focused, 574 direct (two skips), 5,579 ordinary (four skips,
34 headed exclusions), 12 imports, 30 × three settlement scenarios, guard scan
70 rows/391 effects/zero missing admissions and all 67 differential groups pass.
Frozen source/test/component-doc hashes and gate dependency manifests match.
Draft review corrected default-hook eligibility and completed the declared
unsafe-held-root resolve witness before freeze. Initial unprivileged receipt
attempts failed at pytest temporary-directory setup; raw failures and passing
retries are retained, with no product call failure in those setup-only runs.

Evidence root: `build/root-admission-optimization-20260928/`.
Latest manifests/receipts: `executor/held-resolve-*`,
`resume/executor-held-resolve-*`, and differential candidate
`candidate-executor-held-resolve-frozen-86bed156c3414714a9644d28697832fb`.
Independent review: `executor/independent-review-held-resolve-20260928.md`.

## Pending runtime decision

No runtime changes were made. A Codex question asks whether to implement the
bounded duplicate removal in `_resolve_target_path`, or investigate broader
error-preserving admission reuse first. Several other repeated guards preserve
error classification or ordering; the narrow proposal does not claim one
admission across every runtime step. Its implementation awaits the user reply.
Read-only design is complete; refresh native.resolve against this integrated
predecessor before proceeding. Do not interpret the exceeded goal as authority
to retire other guards or as completion of the runtime outcome.

## Preservation

Retain the clean managed baseline checkout at
`C:\Users\Spectrum\.codex\worktrees\root-admission-baseline\NamiSync`, revision
`b8baf42df91e9aeed1402cd029c86ca9ae287b1b`, primary ignored raw/failed evidence,
the original F: source corpus and historical recovery refs `cfcc6ef`, `0a04921`,
`7eb8c19d`. Recovery work was rebuilt, never merged as WIPs. No unrelated
branch/stash/remote changed. No benchmark fixtures or task test processes remain.
K: held-attribute, geometry and stat-serial observations pass; the separate
FileIdInfo compatibility defect remains deferred. No exFAT copy claim.
