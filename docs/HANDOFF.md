# Latest session — executor invocation holds

2026-09-28, `milestone1-adelbert`. Core `6536c04` is integrated. The next
atomic outcome implements executor invocation holds and optional internal
fallback diagnostics, preserving runtime guard dispatch, descendant checks,
physical containment, leaf probes and settlement. Holds release on every exit;
fallback keeps per-access admission. The user explicitly approved the admission
skip after automatic review blocked the original proposal. No oracle re-pin,
stored identity, wire or settlement-policy change is included.

## Verification and observations

Evidence root: `build/root-admission-optimization-20260928/`.

- `resume/executor-ordinary.log`: 5,442 passes, four skips, 34 headed
  deselections. Twelve import contracts pass; unchanged oracle passes 30
  scenarios × three; guard scan covers 70 rows/391 effects, zero missing
  admissions. Full gate input/output hash arrays match.
- Focused executor cases: 387 passes; tools rig/CLI: 89 passes, two skips.
  The subsequent cached-exception traceback correction has its focused witness
  and is included in the full gate. Earlier failed receipts remain retained.
- Differential candidate `candidate-executor-frozen-8912729bf10c4289a4fb7d7fa54ec049`
  passes 32 groups against two identical-producer baseline captures. Seven
  first-checkpoint swaps are prevented by native holds and match full unswapped
  controls; seven pre-execution swaps retain baseline outcomes. No unexpected
  difference. Driver SHA-256:
  `8fbbb0835daaa9c3fbbf9b7f3c95b12ae8cfe1d461c121eaa6233be4337c8b63`.
- Review found an omitted first descendant guard; it was restored before
  acceptance. No supported escape or out-of-root mutation was established.
  The retained before/after regression demonstrates the correction. Frozen
  native source SHA-256:
  `04784bec5786adbb56e23fec26fdd323128d8053d0cdf8330a3f141eccda7a96`.
- Three serialized F:→G: 1,000 × 4 KiB samples: 11.059/11.204/11.708 seconds,
  median 0.349 MiB/s. All copies/readbacks pass, source unchanged, targets
  cleaned by rig manifests. Separate execute-only binding-call counts: anchor
  calls 48,000→6,002, volume-information calls 20,000→6,002, two final-path
  queries. PERFORMANCE owns the limits. The 1 MiB/s goal remains unmet.
- K: exFAT root-scope witness passes. Copy witness truthfully fails with error
  87; read-only queries expose a baseline unconditional FileIdInfo blocker.
  Exact first failing copy API is untraced. BUGS records this deferred
  compatibility finding; no exFAT copy success is claimed.

## Immediate continuation and preservation

Independent source/evidence/document review approved this atomic outcome;
its receipt is `executor/independent-review-20260928.md` under the evidence root.
Read-only design identifies the next measured path reduction;
single-lstat consolidation and preflight/verifier holds remain pending. Preserve
the second directory observation and physical root/descendant resolution unless
the user approves a concrete change. M1_PLAN owns the next-step decision.

Recovery branches remain until final accounting, never merge/cherry-pick as-is:
`codex/wip-20260928-1158-root-hold-binding` at `cfcc6ef` (useful core rebuilt in
`6536c04`; rejected identity mechanics replaced), and
`codex/wip-20260928-1442-executor-hold-approval` at `0a04921` (three draft docs
rebuilt into this outcome). No remote changed; unrelated recoveries/stashes
remain untouched.

Managed baseline worktree:
`C:\Users\Spectrum\.codex\worktrees\root-admission-baseline\NamiSync`,
`b8baf42df91e9aeed1402cd029c86ca9ae287b1b`. Retain it for later differentials.
The preserved F: corpus, ignored raw receipts and K: pytest fixtures remain.
Check resolved owned paths before cleanup; failed-copy scratch is evidence.
Pre-existing pre-invocation root replacement and identity-less DELETE/TRASH
findings remain excluded from this refactor.
