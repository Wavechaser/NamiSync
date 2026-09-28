# Latest session — root-admission optimization closeout

2026-09-28, `milestone1-adelbert`. Integrated core `6536c04`, executor holds
`90b57646`, held attributes `8cdd669`, preflight `4263b12`, verifier holds
`0b85d88`, verifier geometry `e189b48`, executor leaf stat `7e60a47` and bounded
path reuse `5fe5126`. Descendant consolidation is gated and independently approved
in `executor/independent-review-descendant-stat-20260928.md` under the evidence
root; this commit completes it. M1_PLAN is condensed to current policy, shipped outcomes,
commit/evidence pointers and the final outcome; old recovery chronology stays
in Git/evidence.

## Final outcome and verification

Only `_validate_existing_chain`, its native tests and EXECUTOR behavior docs
change in production scope. Every visited descendant including the leaf gets
one checked no-follow observation. Eager conversion refusals and UnsafeExecutionPath
propagate; initial other OSError unavailability stops the walk. All independent
physical, directory, volume and settlement checks remain.

Evidence root: `build/root-admission-optimization-20260928/`.

- `executor/descendant-stat-frozen-inputs.json`: native `933F0A9A`, native tests
  `2B707C56`, EXECUTOR doc `9A9BECC9`. Focused 435 pass; direct 574 pass/two skips.
- `resume/executor-descendant-stat-*`: 5,550 ordinary passes, four skips,
  34 headed deselections; 12 imports, settlement 30 × three and guard scan
  70 rows/391 effects/zero missing admissions. Gate input/output manifests match.
- `differential/runs/candidate-executor-descendant-stat-frozen-81d3bc3ead0c45d9afa4b27d6099715f`:
  all 67 full comparisons pass with unchanged qualified producer/baseline pair;
  13 held swaps block with 32, case fallback remains active, three frozen hashes
  match. Raw receipts and supplemental checker source are retained.
- Serialized three-sample copy median 9.684 seconds (9.155–10.471), 0.403 MiB/s;
  all copies/readbacks pass, source is unchanged, and rig-owned G: targets are
  removed. Separate counts/profiles retain their diagnostic authority and matching
  input manifests. Total stat/existence observations fall by 19,000 across the
  leaf/descendant changes; extended conversions fall 160,030→22,025 across this
  executor pass. Full methods, stage results and limits are in PERFORMANCE.

## Remaining performance decision

The user requested a pause after finishing and committing this round, followed
by a recap. Do not begin the next throughput investigation or optimization until
the user resumes it. Retain the clean baseline checkout for that follow-up.

The 1 MiB/s goal is unmet. Current profile retains 26,000 physical resolutions,
6,000 fresh leaf volume observations and 90,074 spelling validations per fixture.
Inclusive instrumented costs overlap. Every leaf volume lookup currently gets
one fresh anchor and volume result. Retiring/reusing those facts, physical
resolutions or independent descendant/directory checks needs a concrete reviewed
policy decision. No such change is active, and no further production edit is
planned in this pass.

Preflight observation median is 2.722→0.551 seconds; verifier is 3.885→1.512.
K: supports held attributes, handle geometry and preflight observation. Its
FileIdInfo compatibility defect remains deferred in BUGS; no successful exFAT
copy/verification is claimed. Root replacement before invocation and identity-
less DELETE/TRASH replacement remain outside this outcome as recorded in M1.

## Preservation and cleanup

Recovery refs `cfcc6ef`, `0a04921`, `7eb8c19d` are deliberately retained as historical
evidence. Useful work was rebuilt into reviewed core/executor/preflight commits;
rejected identity-comparison/write-sharing proposals are not current policy.
Never merge/cherry-pick recovery WIPs. No unrelated branch/stash/remote changed.

The managed baseline checkout at
`C:\Users\Spectrum\.codex\worktrees\root-admission-baseline\NamiSync` is clean
at `b8baf42df91e9aeed1402cd029c86ca9ae287b1b`, has no active capture process and
contains only disposable ignored bytecode caches. Both authoritative baseline
captures, qualification, sources and all failed receipts are retained under
primary `build/`. Retain the baseline for the requested pause/follow-up; preserve
primary ignored evidence and the original F: corpus. Rig-owned measurement targets have
already been removed by their manifests.
