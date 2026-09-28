# Latest session — bounded executor path reuse

2026-09-28, `milestone1-adelbert`. Integrated core `6536c04`, executor holds
`90b57646`, held attributes `8cdd669`, preflight `4263b12`, verifier holds
`0b85d88`, verifier geometry `e189b48` and executor leaf stat `7e60a47`.
Bounded path reuse is frozen and gated; independent whole-outcome review approves
in `executor/independent-review-path-cache-20260928.md` under the evidence root.

## Current outcome and evidence

Native invocation state retains successful exact absolute conversions for at
most four root/anchor spellings and one last nonroot Win32 spelling. Relative
forms/failures bypass storage; caches clear before scope release and cannot be
reused by copied contexts. Exact already-validated runtime root spelling bypasses
normalization; variants retain it. All actual filesystem observations remain.

Evidence root: `build/root-admission-optimization-20260928/`.

- `executor/path-cache-frozen-inputs.json`: five paths, native `4F7E22CB`, runtime
  `5B6DE694`. Focused 425 pass; direct 574 pass/two symlink privilege skips.
- `resume/executor-path-cache-*`: 5,540 ordinary pass, four skips, 34 headed
  deselections; 12 imports, oracle 30 × three, guard scan 70/391/zero missing
  admissions. Gate manifests match.
- `differential/runs/candidate-executor-path-cache-frozen-2f524e4bcffb437796e8499331ec5645`:
  all 67 full comparisons match the unchanged qualified producer/baseline pair;
  all five frozen hashes match. Supplemental checker source is retained.
- Timing/count/profile receipts use `resume/executor-path-cache-` prefix.
  Three uninstrumented samples median 10.757 seconds (10.656–11.819), 0.363 MiB/s,
  versus preceding 12.365 seconds. All copies/readbacks pass, source is unchanged
  and rig-owned targets are cleaned. Extended conversions 163,030→22,025;
  lexical conversions 77,018→8,018. Actual stat/existence, physical resolutions
  and project-ctypes counts are unchanged. Profile manifests match. These are
  diagnostic measurements, not randomized causal evidence or the 1 MiB/s goal.

## Next outcome

After reviewed cache integration, activate M1's single-lstat descendant walk:
only `_validate_existing_chain`, native tests and EXECUTOR behavior docs. Keep
conversion refusals outside the catch, dispatch the checked observation once per
visited component including the leaf, rethrow unsafe refusals, stop at initial
OSError unavailability. Keep ValueError propagation and every surrounding guard.
Read-only refresh against frozen cache found no additional owner or decision.
No descendant implementation has begun. Leaf volume queries each obtain fresh
mapping/information once; reducing those would change a current check. No such
retirement, physical-resolution retirement or second-is_dir change is authorized.

## Preservation and exclusions

Preflight median observation is 2.722→0.551 seconds; verifier median is
3.885→1.512 seconds, with method limits in PERFORMANCE. K: supports held
attributes, geometry and preflight observation. FileIdInfo compatibility remains
deferred in BUGS; no exFAT copy/verification success is claimed.

Retain recovery refs `7eb8c19d`, `cfcc6ef`, `0a04921` until final accounting; never
merge/cherry-pick WIPs. Preserve ignored evidence/fixtures, the F: corpus and
managed baseline worktree
`C:\Users\Spectrum\.codex\worktrees\root-admission-baseline\NamiSync` at
`b8baf42df91e9aeed1402cd029c86ca9ae287b1b`. No remote or unrelated work changed.
Prior independent reviews remain under their owning evidence directories.
