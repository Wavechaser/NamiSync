# M1 cleanup accounting — 2026-11-11

The user explicitly requested removing the loose codex branches without keeping
superseded recoveries, and removing the external test roots while retaining the
benchmark corpus. The H: source/target human-testing exclusion remains binding.

## Completed

- Removed all six local codex branches listed in branch-audit.json. The attached
  acceptance worktree was detached at cfeac2d9 first; all three secondary
  worktrees and their files/environments remain. No new archive or replacement
  refs were created. Ordinary Git reflogs/objects were not purged.
- Removed precisely 61 registry-matched external NamiSync-resource roots:
  934,265 files, 22,944,192,000 logical bytes (21.37 GiB). This is not a measured
  free-space delta. Preflight validated normalized absolute boundaries, current
  registry matches, and absence of reparse entries throughout the targets.
- Final independent inspection confirms all planned roots absent and no other
  NamiSync-resource roots remaining directly under F: or H:\test_dir.
- Retained F:\NamiSyncExecutorBenchSource (1,582 files / 5,171,478,579 bytes),
  H:\test_dir\source (164 / 23,836,464,560), and H:\test_dir\target
  (205 / 25,214,861,761). Their file counts and total logical sizes match the
  original census. No content hashes were re-collected for these kept trees.

## Evidence and limits

external-cleanup-plan.json records the preflight set and counts;
external-cleanup-journal.jsonl records 61 completed per-root removals;
external-cleanup-result.json records completion; cleanup-verification.json
records independent absence checks, retained census comparisons and worktrees.
The original inventory/report remain historical, not current disk-use figures.

Initial ordinary Git mutations were blocked by sandbox permissions; their
authorized elevated retries succeeded. External deletion also used the approved
filesystem escalation. There were no deletion errors. No remote refs, product
files, tests, build evidence, tester packages or retained worktree files were
removed. Broader build cleanup and document tidying remain pending.

## Build Tiers A + B (later the same day)

The user selected Tiers A and B including SQLite (plan in `build-report.md`).
Removed 151,464 files and 73 dangling in-build junction links (11,127,786,835
bytes, 10.36 GiB) and 27,261 emptied directories; no row changed between plan
and execution. build is now 242 entries, 179,688 files, 6.67 GiB. 1,081 rows
(1.0k old Codex-sandbox-owned files, mostly m1-7-ablation) are access-denied and
remain; rerunning the executor elevated completes them. Every hold was verified
intact. Receipt: `tierab-result.json`.

## Build round 5 (later the same day)

User approved the three deletion rows only ("step 1"); in-place archiving was
not approved. `plan_round5.py` -> `round5-manifest.csv`; executed with
`execute_tiers_ab.py pyi-work frozen2 git-copy` (same re-check, journal and
empty-dir rules). Removed 47,590 files / 1,466,976,007 bytes and 1,094 emptied
directories; 340 Codex-sandbox-owned rows under `*-temp\wheel0\source` denied.
`verify_round5.ps1` confirms worktrees clean, tester set and gui-tuning counts
unchanged, 18 `build_cleanup_*` files, both frozen2 proof ZIPs present.
Build: 196 entries, 131,126 files, 5,779,757,053 bytes. See `round5-result.json`.

## Build round 6: leftover test files (later the same day)

User: "clean the leftover test files first". Closed roots only. `plan_round6.py`
found 256 pytest basetemps that escaped Tier B's `pytest-of-*`/`basetemp`
anchor; removed their non-receipt files (rebuilt wheels included) and
synthetic `.bin`/`.original`/`.restored` payloads elsewhere. Removed 31,604 files
/ 632,408,067 bytes and 7,537 emptied directories; 455 sandbox-denied. Holds
re-verified. Build: 196 entries, 99,527 files, 5,158,377,554 bytes
(`round6-result.json`).

## Build round 7: retention policy applied (2026-11-14)

User authorized removing the three secondary worktrees, R5 packages,
`m1-token-audit-*` and gui-tuning HDR captures, keeping M1_PLAN-cited material
at least partially, and clearing everything not cited by persistent docs.
Worktrees were clean with HEADs on main and were removed with `git worktree
remove`. `measure_policy.py` classed citers (lasting / M1_PLAN / CHANGELOG /
HANDOFF / obsolete / code); `plan_round7.py` kept lasting-cited files (minus
HDR captures) and M1_PLAN-cited text records outside workspace trees. Removed
64,303 files / 4,175,011,772 bytes and 24,282 emptied directories; 1,347
sandbox-denied. Build: 103 entries, 20,122 files, 1,296,885,948 bytes
(`round7-result.json`).
