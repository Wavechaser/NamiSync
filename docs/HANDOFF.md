# Latest session — per-access held-handle guard

2026-09-28, `milestone1-adelbert`, core/executor correction over `90b57646`.
The user rejected denying write sharing and approved checking current attributes
on the held handle before admission reuse. Core now provides `require_ordinary()`;
all three executor reuse sites call it. The query uses FileBasicInfo0, rejects
reparse/placeholder state and propagates query failure without authorizing access.
Diagnostics stay query-free; one final-path confirmation and existing sharing,
root flushes, descendant checks and physical resolution remain unchanged.

## Verified evidence

Evidence root: `build/root-admission-optimization-20260928/`.

- `rootguard/native-basic-first.json`: attribute-only and generic-write handles
  convert an empty held NTFS root, and the original handle sees attributes
  change from 16 to 1040. Nonempty root/ancestor conversion fails with 145; held-root
  removal fails with 32. Reparse metadata is restored, root flush and ordinary child
  operations succeed, all handles close. No redirected executor effect was run.
- K: EXFAT BA1F1F45 rejects FileAttributeTagInfo9 with 87 but accepts BasicInfo0;
  both receipts remain. Production `require_ordinary()` lifetime tests on K:
  pass twice, including exceptional exit and descendant operations.
- 541 affected tests and 22 focused guard cases pass, including all three real
  conversion refusal sites, placeholder classification and failed native query.
  No tests were retired. `rootguard/frozen-inputs.json` binds seven builder files.
  Core SHA256 `6FBA7B3AEB37B316C99D4EDC4EF229FCF71D830715A7BAA12A1A36A12E1084B4`;
  executor native `7E68306B01BCDF983AE25204E82AA892AAF6EB898D70C14494B7FE5CFA4E1C17`.
- `resume/held-attributes-*`: 5,462 ordinary passes, four skips, 34 headed
  deselections; 12 imports; unchanged settlement oracle 30 × 3; guard scan 70 rows/
  391 effects/zero missing admissions. Input/output hash arrays match.
- Differential candidate `candidate-held-attributes-frozen-7d89ad8690664fc0b808996f1ec8315c`
  passes 46 groups with unchanged producer 243d2173 and all frozen hashes matching.
  Seven executor swaps are blocked and match full controls. The 14 preflight
  groups still exercise baseline behavior because preflight is not restored yet.
- Fresh independent source/test/evidence review has no unresolved finding.
  Serialized guarded measurements take 15.271/15.711/15.047 seconds for
  1,000 × 4 KiB F:→G: copies, median 0.256 MiB/s. All copies/readbacks pass,
  source unchanged, manifest cleanup complete. Goal remains unmet. PERFORMANCE
  preserves both these and the historical unchecked-hold measurements.

## Immediate continuation

Fresh whole-outcome review approved the complete core/executor correction;
receipt: `rootguard/independent-review-held-attributes-20260928.md`.
Then rebuild preflight from recovery7eb8c19d: only `modules/preflight.py`,
`tests/test_preflight.py` and `docs/PREFLIGHT.md`, not its old stop documents.
Before its sole cached-admission return, call `hold.require_ordinary()`;
all five backend families already pass through that helper. Preserve invocation
invalidation, custom dispatch, typed error policy, physical/leaf/parent/trash
checks. Add the conversion/placeholder/query-failure regression, then rerun its
focused/direct/full/differential gates and isolated measurements. Commit it
separately, then implement verifier. Further executor optimization comes last;
no descendant-check retirement is authorized by probability arguments alone.

## Recovery and exclusions

`codex/wip-20260928-1549-root-write-sharing` at7eb8c19d preserves preflight's
83focused/314direct/46differential partial evidence and the interrupted broad
run. Never merge/cherry-pick it as-is. The root-guard correction replaces its
rejected deny-write proposal; preflight product work must be rebuilt and reviewed.
Keep earlier recovery refs cfcc6ef and0a04921 and the managed baseline worktree
`C:\Users\Spectrum\.codex\worktrees\root-admission-baseline\NamiSync` at
b8baf42df91e9aeed1402cd029c86ca9ae287b1b until final accounting. Evidence manifest
`root-write-sharing-recovery-manifest.json` preserves13,351 entries from the stop.

No remote changed, unrelated stashes/branches remain untouched, and native
fixtures/evidence have not been cleaned. The pre-existing K: copy/FileIdInfo
compatibility issue remains deferred in BUGS; the current guard does not claim
an exFAT copy fix. Verifier files and stored identity/wire/settlement contracts
remain unchanged. DEFENSE's existing quiescence assumption covers check/use.
