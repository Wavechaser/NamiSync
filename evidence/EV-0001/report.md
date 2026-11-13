# M1 mop-up survey — 2026-11-11

Historical survey. The subsequent user-authorized deletions and superseding
recovery-retention decision are recorded in `cleanup.md` and M1_PLAN.

Inspected HEAD `41ce4e89f177c1c5457e2c631f513c338b5b49b0`. No deletion, branch
pruning, worktree removal, fetch or remote mutation occurred.

## Footprint

| Scope | Entries | Files | GiB |
| --- | ---: | ---: | ---: |
| F: root, NamiSync-named entries only | 22 | 240,582 | 4.86 |
| H:\test_dir, all immediate entries | 42 | 695,634 | 67.01 |
| Repository build, excluding this survey | 432 | 331,152 | 17.04 |

Sizes are logical file lengths, not allocated/reclaimable space. Hard links may
be counted repeatedly. All 579 issues are skipped build reparse points; there
were no enumeration errors. This live census is not a deletion manifest.
Other F: root entries were listed but not traversed; they are out of scope.
CIM process checking was denied, so environment idleness is not established.

## External roots

- **Keep by explicit user instruction:** H:\test_dir\source (22.20 GiB) and
  target (23.48 GiB) are human-testing play directories. Exclude both whole
  trees, including `.synctrash`, from cleanup.
- **Candidates:** all 61 existing NamiSync-resource roots have exact path
  matches in retained fixtures.jsonl registries (62 registry files searched).
  Total 21.37 GiB; five 4 GiB payload targets account for 20 GiB. Registry
  membership establishes provenance, not unchanged descendants. Re-inventory
  exact targets before deletion and preserve manifests, registries, samples,
  original/failed receipts and screenshots separately.
- **Hold:** F:\NamiSyncExecutorBenchSource, 4.82 GiB / 1,582 files. PERFORMANCE
  describes its five-band baseline corpus; the original generator seed was not
  reconstructed. Archive exact bytes or obtain a deliberate disposal decision.

Excluding the user's play directories leaves about 43.22 GiB surveyed, of which
only 21.37 GiB is classified as registered external fixture candidates.

## Build priorities

| Root | GiB | Largest immediate populations |
| --- | ---: | --- |
| m1-release-repair-20261110 | 4.87 | acceptance 3.31; runtime 0.89; portable 0.32; renewal 0.17 |
| m1-r4-20261109 | 2.38 | soak 1.61; gallery-diag 0.47; two package trees about 0.10 each |
| m1-release-20261104 | 1.09 | historical release/build/CI trees; finer classification pending |
| m1-r5-20261111 | 0.98 | acceptance 0.81; checkout 0.08; portable 0.04 |
| close-probe-20261108 | 0.63 | old/new installed diagnostic populations |

The top four total about 9.32 GiB. These are mixed evidence/environment trees,
not deletion estimates. Classify generated fixtures, installed environments,
extractions and caches against their instructions and identity records next.
PERFORMANCE requires preserving irreplaceable raw evidence before cleanup.
Keep final tester material in dist/v0.1.0, outside this census.

Previous cleanup removed about 21.32 GiB through November 4. Its surviving source
bundle/mapping, fixture capsule, baseline patch and receipts are recovery assets.
Some historical directories are intentionally incomplete after those reductions.

Three secondary worktrees have clean Git status: R5 checkout at b0a3fe13,
repair acceptance-checkout at cfeac2d9, repair idle-followup-checkout at 1d936876.
Clean status does not account for ignored environments/evidence. Account for
these, then remove worktrees through Git; do not erase their parent roots.

## Local codex branches

| Suffix after codex/ | Tip | Pruning assessment |
| --- | --- | --- |
| m1-release-repeatable | b3095886 | Ready: fully integrated, no worktree. |
| release-repair-authority-v2 | cfeac2d9 | Integrated; remove its clean acceptance worktree through Git first. |
| m1-12-verification-recovery-20261030 | 7b0744d4 | Superseded pause documentation, confirmed in M1_PLAN. Archive unique commit before pruning. |
| m1-release-repeatable-recovery-20261105 | 987cba84 | Rebuilt into b3095886, closed in aefd5b84. Archive before pruning. |
| wip-20261109-0022-table-cadence | ce09180e | Rebuilt with approved cadence revision; M1_PLAN explicitly retains reference/evidence. Keep pending archive disposition. |
| wip-20261110-release-repair | ed18ad3e | Rebuilt into cfeac2d9 and later release. Archive and document saved-change accounting before pruning. |

Each recovery branch has one commit unreachable from HEAD; git cherry reports
distinct patches. Do not merge/cherry-pick WIP just to make pruning possible.
For 987cba84, five saved entries exactly match b3095886; three documentation
entries evolved and code/test corrections explicitly fix archive newlines and
stage the fixture README. For ed18ad3e, 36/40 saved paths match cfeac2d9 exactly
(including deleted-file absence); three documentation entries evolved and the
transport test was revised for reviewed v2 authority. Cadence reconstruction
and pause-document supersession are recorded in M1_PLAN.

Recommended sequence: create a self-contained bundle of all four recovery tips,
verify and restore/check tips in a fresh disposable repository, record archive
location/dispositions in M1_PLAN, remove accounted worktrees with Git, then prune
branch names. Keep the archive outside any deletion set. No bundle was created.
Remote findings are limited to existing local remote-tracking state.

## Evidence

- inventory.csv, survey-summary.json, issues.json: complete scoped census.
- detail-inventory.csv: breakdown of the three selected large build roots.
- fixture-registry-paths.txt, external-root-owners.csv: external provenance.
- branch-audit.json: tips, ahead/behind counts, unique commits and patch checks.
- recovery-path-accounting.csv: saved-path comparisons against successors.

Scripts here reproduce read-only checks. This directory is the survey's only
new ignored artifact population; it is excluded from the footprint totals.
