# build\ survey — 2026-11-11 (read-only)

HEAD `41ce4e89`. Nothing deleted, moved or re-permissioned. Scripts:
`build-survey.ps1`, `build-categories.ps1`, `build-citations.ps1`; outputs the
matching `.csv` files. Sizes are logical bytes; categories are path/extension
heuristics, i.e. estimates, not deletion manifests.

## Footprint

433 top-level entries (334 dirs, 99 loose files), 331,152 files, 17.04 GiB.
579 reparse points skipped; zero access-denied directories.
Rounds 1-3 (to 2026-11-04) already removed 21.3 GiB and left 3.8 GiB. Roots
touched since 2026-11-05 hold 15.3 GiB, so nearly all current bulk is release-
and measurement-phase output that has never been through a cleanup round.

## Citation classes (tracked files outside build\)

| Class | Entries | Files | MiB |
| --- | ---: | ---: | ---: |
| Cited by an active doc / workflow / tool | 124 | 301,357 | 16,424 |
| Cited only by docs/obsolete | 27 | 23,366 | 695 |
| Uncited | 282 | 6,429 | 328 |

Citing files: PERFORMANCE 111, M1_PLAN 105, BUGS 21, TOOLS 13, TESTS 6,
HANDOFF 5, CHANGELOG 4, obsolete docs ~137. Deleting whole uncited/obsolete
roots frees at most about 1 GiB; the space is inside cited roots.

## Content of all roots by category (estimate)

| Category | MiB | Retention basis |
| --- | ---: | --- |
| WebView2 / browser profiles | 3,731 | Regenerable; keep profile identity facts |
| Packaged/extracted bundles, .exe/.dll/.pyd/.pkg/.pyz | 3,365 | Regenerable only where source ZIP + hash retained |
| SQLite (.db/-wal/-shm) | 2,681 | Seeded fixtures regenerable; failure inputs are not |
| Receipts (json/md/log/xml/csv/py/...) | 2,102 | Keep |
| Installed environments / runtimes | 1,795 | Regenerable (PERFORMANCE "Evidence retention") |
| pytest fixture trees | 1,734 | Regenerable after receipts kept |
| Archives (zip/whl/bundle) | 808 | Keep (identity anchors) |
| Images | 498 | Keep (captures) |
| Secondary worktrees (3) | 204 | Git-managed; remove via `git worktree remove` |

## Largest roots

| Root | MiB | Dominant populations |
| --- | ---: | --- |
| m1-release-repair-20261110 | 4,984 | acceptance 3,388 (profiles 1.6 GiB, pytest 0.7); runtime 907; portable 330 |
| m1-r4-20261109 | 2,442 | soak/profiles 1,589; gallery-diag 484; package, package-2 107 each |
| m1-release-20261104 | 1,115 | repeatable 505; attempt-01..06 ~108 each |
| m1-r5-20261111 | 1,000 | acceptance 829; checkout (worktree) 77; delivery + draft 25 each |
| close-probe-20261108 | 641 | pkg 472; app 169 |
| m1-r2-20261109 | 617 | attempt-01..04 ~108 each; env 41; three checkouts |
| dom-costs-20261109 | 603 | measurement 534 (mostly SQLite) |
| gui-tuning | 408 | halo-10bit captures 407 (images; held in rounds 2-3) |
| cadence-measurement-20261108 | 392 | runs 372 (SQLite) |

## Tier A + B plan (executed 2026-11-11; see cleanup.md / tierab-result.json)

`plan_tiers_ab.py` -> `tierab-manifest.csv` (path, size, mtime, rule, proof) and
`tierab-plan.json`. `execute_tiers_ab.py RULE...` re-checks each row (inside
build, unchanged size/mtime, link rows still junctions into build) before removal,
journals to `tierab-journal.jsonl`, then rmdirs emptied directories; `--verify`
checks absence.

| Rule | Files | MiB | Basis |
| --- | ---: | ---: | --- |
| A obsolete-only | 23,327 | 694 | Roots cited only by docs/obsolete |
| A uncited | 6,116 | 187 | No tracked citation; 22 dangling test junctions removed as links |
| B venv | 79,155 | 875 | Installed environments; pyvenv.cfg + dist-info kept |
| B runtime | 3,433 | 147 | Astral 3.13.18 alternative interpreter; no retained venv uses it |
| B pytest | 22,206 | 2,014 | pytest temp state; receipt/capture/zip/whl/bundle files kept |
| B frozen | 12,370 | 1,126 | Extracted apps matching a retained ZIP by path, size, CRC32 |
| B sqlite (opt-in) | 6,011 | 5,605 | App ledgers/history and measurement DBs; rerun-regenerable only |

Extra holds: 24 uncited entries (6.9 MiB) that retained receipts name
(`tiera-receipt-cited.txt`); exactly cited file paths; `runtime\python` (home
of both worktree venvs); 13 frozen trees without a matching ZIP (memory-probe,
freezer-probe, rail-fix-native, close-probe pkg).

## Further reduction measurements (after A + B; nothing removed)

Start: 242 entries, 179,688 files, 6.67 GiB. `measure_round5.py`,
`measure_dupes.py`, `measure_archive.py` -> `round5-candidates.csv`,
`round5-dupes.csv`, `round6-archive-estimate.csv`.

| Candidate | Files | MiB | Proof |
| --- | ---: | ---: | --- |
| PyInstaller work intermediates (23 builds) | 161 | 854 | `.pkg`/`PYZ`/pre-collect exe/base_library beside kept dist + ZIP |
| App trees matching a ZIP elsewhere in build | 1,554 | 247 | path, size, CRC32 (5 trees still unmatched) |
| Byte copies of Git-reachable blobs | 46,215 | 299 | blob id reachable from refs |
| In-place ZIP of 154 closed roots (not release roots, gui-tuning, survey) | 85,864 -> 154 | 2,990 -> 934 | lossless; verify member SHA-256 before removal |
| Byte-identical duplicates >= 256 KiB | - | 754 | overlaps the above; not proposed |

Deletions + archiving together project about 3.2 GiB and about 46k files.

Round 5 (the three deletion rows) executed 2026-11-11 via `plan_round5.py` ->
`round5-manifest.csv` and `execute_tiers_ab.py pyi-work frozen2 git-copy`:
47,590 files / 1.37 GiB removed, 340 sandbox-denied. Build now 196 entries,
131,126 files, 5.38 GiB (`round5-result.json`). Archiving was not authorized.

## What fills the 154 closed roots (after round 5)

86,204 files / 2,991 MiB (`measure_closed_classes.py`, `closed-roots-*.csv`).
Release roots hold 1.9 GiB more; gui-tuning 0.4 GiB.

| Class | Files | MiB | What it is |
| --- | ---: | ---: | --- |
| Results (json/xml/log/md/txt) | 16,177 | 995 | The measurements; 10 MiB DOM/plan snapshot JSONs dominate |
| pytest temp, receipt extensions | 16,666 | 528 | Escaped Tier B (basetemps named `*-temp-*`, `tmp-native-*`): 200 rebuilt wheels 142, fixture JSON 250, screenshots 129 |
| pytest temp, other | 7,807 | 387 | Copy-test payloads (8 MiB source/target/.synctrash), staged sources |
| Synthetic payload trees | 31,387 | 302 | Copy-benchmark trees of 1k-13k tiny `.bin` (77 MiB, 23k files), `.original`/`.restored` 59, install source copies 126 |
| Source snapshots | 9,641 | 301 | Baseline/candidate code copies for differential studies (not in Git) |
| Packages | 116 | 218 | Per-study wheels, dev ZIPs, recovery bundles |
| Third-party installers | 4 | 75 | Node ZIP, Python installer, WebView2 nupkg |
| Images / other | 4,406 | 184 | Captures; misc |

Round 6 (leftover test files, `plan_round6.py`) then removed 31,604 files /
603 MiB from those roots; 455 sandbox-denied. Build: 99,527 files, 4.80 GiB.

## Holds carried forward

HANDOFF: raw evidence, failed receipts, prior cleanup reconstruction assets
(`build_cleanup_*`, about 140 MiB of the loose files), all worktrees and the
final tester set (dist/v0.1.0, R5 delivery). PERFORMANCE "Evidence retention"
governs what inside evidence roots is eligible.
