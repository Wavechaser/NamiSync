# Latest session — executor single leaf observation

2026-09-28, `milestone1-adelbert`. Integrated core `6536c04`, executor holds
`90b57646`, held-attribute correction `8cdd669`, preflight `4263b12`, verifier
holds `0b85d88` and opened-handle geometry `e189b48`. Single-leaf observation
is implemented and gated; fresh whole-outcome review approves its atomic commit
in `executor/independent-review-single-stat-20260928.md` under the evidence root.

## Current outcome and evidence

Executor `_stat_path` uses its checked no-follow snapshot for all metadata.
Eager path validation, unavailable-to-None handling, unsafe refusals, later type/
volume errors and public/subclass dispatch remain. Root attributes, second root
directory observations, descendants, physical resolutions and settlement remain.

Evidence root: `build/root-admission-optimization-20260928/`.

- `executor/single-stat-frozen-inputs.json`: native `F28C0DF6`, tests `5FCD914A`,
  EXECUTOR doc `510E1E5F`. Focused 414 pass; direct 574 pass/two privilege skips.
- `resume/executor-single-stat-*`: 5,529 ordinary pass, four skips, 34 headed
  deselections; 12 imports, oracle 30 × three, guard scan 70/391/zero missing
  admissions. Gate input/output hashes match.
- `differential/runs/candidate-executor-single-stat-frozen-e3c56eeedb584ac2bc00212a46a9b390`:
  all 67 full comparisons match, unchanged qualified producer `e7ba9b8d` and
  baseline pair. Frozen hashes match. Supplemental checker source is retained.
- `resume/executor-single-stat-{timing,counts,counted}.json` and profile receipts:
  three uninstrumented samples median 12.365 seconds (11.934–13.104), 0.316 MiB/s;
  prior guarded median 15.271 seconds. Every copy/readback passes, source remains
  unchanged and rig-owned targets are cleaned. Separate profile finds 12,000
  fewer stat/existence observations, unchanged 26,000 physical resolutions;
  project-ctypes counts unchanged. Pure path conversions rise by 3,000 as missing
  leaves reach the checked observation. Profiles are not throughput evidence.

## Next outcome

After committing this reviewed outcome, activate bounded pure path reuse in M1:
up to four exact absolute root/reviewed-anchor spellings plus one last-successful
nonroot Win32 conversion slot. Root hits must not evict that slot. Cache only
successful pure conversions, bypass relative forms, preserve error timing and
invalidate/clear before scope exit including copied contexts. Runtime exact
reviewed-root spelling can bypass repeated lexical normalization; variants keep
existing checks. Refresh the design against the integrated leaf change first.
No actual filesystem observation or descendant/physical check retirement is
approved by this outcome. No next-outcome product edits have started.

## Preservation and exclusions

The 1 MiB/s executor goal remains unmet. Preflight median observation is
2.722→0.551 seconds; verifier held/geometry median is 3.885→1.512 seconds, each
with method limits in PERFORMANCE. K: supports held attributes, geometry and
preflight observation. Its separate FileIdInfo compatibility defect is deferred
in BUGS; no exFAT copy/verification success is claimed.

Retain recovery refs `7eb8c19d`, `cfcc6ef`, `0a04921` until final accounting; never
merge/cherry-pick WIPs. Preserve ignored evidence/fixtures, the F: corpus and the
managed baseline worktree
`C:\Users\Spectrum\.codex\worktrees\root-admission-baseline\NamiSync` at
`b8baf42df91e9aeed1402cd029c86ca9ae287b1b`. No remote or unrelated work changed.
Prior independent review receipts remain under their owning evidence directories.
