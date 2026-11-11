# Latest session — post-M1 cleanup, 2026-11-11

M1 building and validation are concluded. The user explicitly authorized clearing
all six local codex branches without preserving superseded recoveries, and the
61 registered external resource-test roots. M1_PLAN owns the disposition; earlier
instructions to retain these recovery references are superseded by that decision.

## Changes

- All six local codex branches removed. No archive or replacement refs created.
  Git may retain deleted-tip objects through ordinary reflogs; no object purge
  or garbage collection was requested or run.
- The acceptance worktree is detached at cfeac2d9; its files/environment remain.
  The R5 checkout (b0a3fe13) and idle-followup checkout (1d936876) also remain.
- External cleanup removed all 61 registry-matched roots (934,265 files,
  22,944,192,000 logical bytes / 21.37 GiB). The
  pre-deletion census checked boundaries, registries and every descendant for
  reparse state. Receipts: build/mop-up-survey-20261111/external-cleanup-*.
- Independent post-check finds zero resource-test roots or local codex branches;
  retained directories' file counts and total sizes match the survey baseline.
  Verification: build/mop-up-survey-20261111/cleanup-verification.json.
- Keep F:\NamiSyncExecutorBenchSource, H:\test_dir\source and H:\test_dir\target.
  Both H: directories, including their trash, are the user's human-testing trees.
- Build Tiers A + B (user-selected, with SQLite) removed 151,464 files and 73
  dangling in-build junctions: 10.36 GiB, build now 242 entries / 6.67 GiB.
  Plan, holds and verification: build/mop-up-survey-20261111/build-report.md,
  cleanup.md and tierab-result.json. Worktrees, their venv runtime, R5 delivery,
  proof ZIPs and receipt-cited entries verified intact.
- 1,081 rows (old Codex-sandbox-owned files, mostly m1-7-ablation) were denied.
  From an elevated PowerShell in the repo, rerun
  `.venv\Scripts\python.exe -I build\mop-up-survey-20261111\execute_tiers_ab.py obsolete-only uncited venv`,
  then `--verify` with the same rules.
- Documentation tidying remains pending. Earlier census numbers in report.md
  describe the pre-cleanup state.

## Evidence and next work

Survey/cleanup tooling and receipts live in build/mop-up-survey-20261111/.
The original inventory and branch audit retain provenance, not Git recovery
archives. Tier A removed whole uncited/obsolete-only entries, including their
old failure records, by user decision. Keep receipts in cited roots, prior cleanup
reconstruction assets, all remaining worktrees and the final tester set. Remaining build is evidence receipts plus holds; Tier C (removing the three
secondary worktrees through Git) is not authorized yet. No product/test
changes or product test runs in this session.

Final tester candidate remains b0a3fe133745b2212b8c7d1254c317879e980f90 (Package05),
ZIP SHA-256 652c55ca3c2ace0903732490ead0b907ac726dba5af4155aa5345db80c8e9efc.
Prior release gate: 6,575 passes, four skips, 35 headed cases, 12 import contracts;
packaged Medium witness passed. Tester set: dist/v0.1.0 and R5 delivery/;
release evidence: build/m1-r5-20261111 and earlier repair/R4 roots. Nothing
published or sent here. Keep M1 headings pending delivery; separate README
revision remains pending. The terms file was not legally reviewed.
