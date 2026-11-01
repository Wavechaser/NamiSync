# Latest session — M1-12 verification complete, 2026-10-30

M1-12 was authorized from clean `b22a2943`. Independent lifecycle review found
no blocking supported defect in its finite corpus; product and tests are
unchanged. Completed gates: 717 composition tests, 6,326 ordinary tests with
four WinError 1314 symlink-privilege skips, twelve import contracts, and the
pinned settlement oracle (30 scenarios × 3 runs).

All 35 installed headed obligations now pass. After the user resumed native
verification, the five outstanding execution/Inventory/task-shell journeys
passed unchanged in 60.10 seconds. Earlier attempts refused foreground input;
their original failures remain retained. Shell receipts prove Plan Again had
already succeeded before those focus refusals. No guard was relaxed.

[M1_PLAN](M1_PLAN.md) records V1–V4 closure. Source/test/helper dependencies were
unchanged, and source/wheel hashes were revalidated before reusing prior passes.
Evidence, exact installed identities, failures, captures, hashes and independent
reviews are in `build/m1-12-20261030/`; `headed-resume.log` and the 34 preserved
resumed artifacts close the native gap. Recovery `7b0744d4` on
`codex/m1-12-verification-recovery-20261030` contains superseded pause docs only;
it remains historical preservation, never a merge/cherry-pick unit. The verified
closeout is rebuilt from current records. Release and DOC-2 remain inactive.

Concurrent build-cleanup documentation is separate work retained in the working
tree and excluded from this checkpoint commit. Its exact pre-edit handoff and
diff are preserved in the M1-12 evidence root.

## Concurrent build artifact reduction

The authorized continuation restored read access to the two protected wheel
files in `ab8-20260926` and `m1-7`, preserving owners and contents. It removed
114,320 files / 8.48 GiB logical bytes: verified reconstructible source copies,
preserved fixture payload copies and bytecode. All 183,350 retained files in
the affected roots matched their original hashes; the deletion journal matched
the frozen manifest, with no verification failures. Must-keeps remain intact.

Round 2 then removed 239,978 files / 5.91 GiB and 156,445 emptied directories:
proven wheel staging, RECORD-verified venv files, per-test pytest state and
uncited scratch roots. 55,793 of those files sat in Codex-sandbox-owned trees and
needed an elevated run (`build/build_cleanup_round2_elevated.ps1`) with the same
per-file checks. Verification: all targets absent, journal equals manifest, and
157,634 retained files unchanged. The only difference is the batch script itself,
edited after planning to add resume support. Holds and proofs:
`build/build_cleanup_round2_summary.json`.

Cumulative cleanup is 674,132 files / 19.77 GiB logical bytes. The final census
is 157,642 files / 5.31 GiB in 63,936 directories, including audit artifacts;
this is not a measurement of free disk-space change. Exact receipts and recovery
pointers are in `build/build_cleanup_reduction_summary.json` and
`build/build_cleanup_round2_summary.json`. Source reconstruction was
verified from an independently unpacked bundle; fixture bytes and original
filesystem facts remain in the capsule and manifest. Restore only absent paths
and verify hashes; never overwrite retained modifications. Unmatched source,
Git metadata, recent/active work and unaccounted payloads remain held.

Product and test code are unchanged; verification covers filesystem contents,
recovery artifacts and documentation. Concurrent M1-12 work is governed by
M1_PLAN; this cleanup neither changes its scope nor supplies product acceptance.

Immediate recovery context from the preceding session follows.

The user authorized auditing and pruning the five remaining local codex/*
recovery/rebuild branches. Their useful work is integrated or superseded:
C1 matches the 1f0eb086 test patch; Inventory Follow matches the 4fceac7b tree;
Verify-table accounting covers all 48 saved path entries; the controller WIP
was rebuilt in 5e505fbc, which is already in milestone1. M1_PLAN records each
branch and its disposition.

The original five tips and their complete histories are retained in the verified
build/m1-closeout-study-20261029/results/recovery-branches-20261030.bundle.
The adjacent branch-cleanup-20261030.json records accounting, bundle identity,
and before/after refs, stashes and worktree checks. Independent review covers
the controller recovery/rebuild comparison. Product tests and timing measurements
are unnecessary for branch/documentation cleanup and were not run.

Only the five named local branch refs are removed. Stashes, remote branches,
hidden Codex refs, original failed receipts and the D2 approval-block snapshot
remain. No source, test or product change, push, worktree removal or history
rewrite is included. Release and DOC-2 remain inactive.
