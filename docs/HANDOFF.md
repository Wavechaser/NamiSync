# Latest session — verifier geometry and executor continuation

2026-09-28, `milestone1-adelbert`. Integrated: core `6536c04`, executor holds
`90b57646`, current held-attribute correction `8cdd669`, preflight `4263b12`,
verifier invocation holds `0b85d88`. Opened-handle geometry is fully verified and
independently approved for its atomic commit.

## Geometry outcome

Only verifier native.py, its native/engine tests and VERIFIER behavior docs
changed. FileStorageInfo16 supplies positive logical sector size from the opened
unbuffered file. Unavailable/zero information falls back to the old fresh path
query. Failed open still queries old geometry before re-raising, preserving
dual-failure precedence. All successful opens close on every subsequent failure.
Root/descendant/final-path guards, four file snapshots, sharing, identity,
classification, recording, public contracts and supported filesystems remain.

Evidence root: `build/root-admission-optimization-20260928/`.

- `verifier/geometry-frozen-inputs.json`: four source/test/doc hashes; native
  `384CC16E`. Final focused 144 pass, direct 479 pass/two symlink privilege skips.
  The first default-temp setup failure and corrected 132-pass baseline remain.
- `resume/verifier-geometry-*`: 5,514 ordinary passes, four skips, 34 headed
  deselections; 12 imports, unchanged oracle 30 × three, guard scan 70 rows/
  391 effects/zero missing admissions. Gate input/output manifests match.
- `differential/runs/candidate-verifier-geometry-frozen-513d81cb54ab48e69b0ea2ee46e0fc53`:
  67 groups, zero unexpected differences, same qualified producer `e7ba9b8d`
  and baseline pair. Held swaps block with 32; active case fallback and custom
  remount/identity-weak controls stay strict. Four frozen hashes match; engine
  `0A5A5002` and tools tap `41670E93` remain unchanged. Checker source is retained.
- `verifier/geometry-verify-{timing,counts,counted}.json`: three serialized
  timings, median 1.512 seconds (1.267–1.551), versus held median 1.998 and
  original baseline 3.885. Separate counts: one anchor/volume query each, 1,000
  handle-sector queries, zero pathname-sector queries, 1,999 root attributes
  and unchanged 12,000 file-information queries. All 1,000 files verified/applied;
  read bytes, command IDs, source observations and product manifests match.
- Independent whole-outcome review approves source, tests, gates, measurements
  and docs: `verifier/independent-review-geometry-20260928.md`.

## Next executor outcome

The read-only inspection recommends a separate `_stat_path` single-lstat commit,
already authorized by the user/M1. It currently never compares its observations;
reuse the checked no-follow snapshot for kind and all metadata, preserve initial
unavailable→None policy, rethrow UnsafeExecutionPath (an OSError subclass), and
keep volume failures outside that catch. Preserve subclass/public dispatch and
all root, descendant, physical and settlement checks. Activate its finite
native.py/native-tests/EXECUTOR-doc population and gate in M1 after geometry commits.
No executor implementation changes have started.

The new `resume/executor-after-verifier-profile.{prof,txt,json}` plus `-run.json`
profile only executor caller-thread work on 1,000 × 4 KiB F:→fresh G:. All copies
and readbacks pass, source observations/inputs match and rig cleanup completes.
The instrumented 32.4 seconds is not throughput evidence. It shows 160,030
extended-path conversions, 435,084 spelling validations, 26,000 physical resolves
and 9,000 `_stat_path` calls. Inclusive costs overlap. Pure invocation-local path
reuse is a later measured outcome; no descendant or physical check retirement
is inferred. Existing retained copy paths rule out an indiscriminate full-plan map.

## Preservation and exclusions

Corrected uninstrumented executor median remains 15.271 seconds / 0.256 MiB/s,
below the 1 MiB/s goal. Earlier unchecked-hold timings are historical. Preflight
observation median is 2.722→0.551 seconds, including prior core improvements.
K: supports held-attribute and geometry queries plus preflight observations;
the separate FileIdInfo compatibility defect remains deferred in BUGS. No exFAT
copy/verification success is claimed. DEFENSE quiescence covers check/use.

Retain recovery refs `7eb8c19d`, `cfcc6ef`, `0a04921` until final accounting;
never merge/cherry-pick WIPs. Preserve ignored receipts/fixtures, F: corpus and
managed baseline worktree
`C:\Users\Spectrum\.codex\worktrees\root-admission-baseline\NamiSync` at
`b8baf42df91e9aeed1402cd029c86ca9ae287b1b`. No remote, unrelated stash/branch or
user work changed. Prior independent review receipts remain under the owning
`rootguard/`, `preflight/` and `verifier/` evidence directories.
