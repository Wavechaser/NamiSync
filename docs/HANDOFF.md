# Latest session — policy-driven executor simplification

2026-09-29, `milestone1-adelbert`, starting clean at `9b694e0a`.
The equivalence baseline remains `b1b58476`; policy refinements are committed
as `dadc1fe`. The user authorized results 1–3 and small atomic commits using
execute-task. Direct writes remain deferred.

## Current outcome

The source-only consolidation candidate reuses fresh COPY/MOVE_UPDATE source
fidelity, retains retry and all target checks, removes final source admissions
where no source access remains, and retires retained-target refusal precedence.
UPDATE, public contracts, native primitives and pipeline APIs are unchanged.

Automatic approval review rejected target-fidelity consolidation even after
explicit user approval; those edits remain unapplied. The source-only safer
alternative passed review. No rejection was bypassed.

The next handle-continuity outcome is recorded in M1_PLAN. The user explicitly
approved retaining already-granted handle rights when copied/inherited ACLs
would prevent old finishing reopens or path publication. Native witnesses and
restored-ACL receipts are under `build/executor-simplification-20260929/handle-acl-witness/`.
No handle implementation has begun.

## Verification

Evidence root: `build/executor-simplification-20260929/`.

- Focused candidate checks: 37 passed. Initial native/runtime baseline: 305 passed.
- Native executor/workflow/tools neighborhood: 1,792 passed, three skips.
- Ordinary suite after the oracle pin change: 5,611 passed, four unavailable
  symlink-privilege skips, 34 deselected; `differential/result1-ordinary.log`.
- Import contracts: all 12 kept. Guard scan: 70 rows, 391 effects, zero missing
  admissions; source/effect fidelity independently inspected.
- Candidate oracle capture and precommit custom-baseline check: 30 scenarios
  times three. Independent review classified 27 deletion-only source-probe
  rows and 43 unchanged rows; all settlement fields remain exact. Approved
  semantic pin: `2509b4e543afb32efdc347149a34be05838335c59fc86b71b1b56ecee82f22a9`.
  Official committed-baseline check must run after the atomic commit.
- Differential: all 67 groups, zero compared-result differences. Raw captures
  are `differential/runs/baseline-b1b58476-1677e16405314dbfbe06e27ba745d8e6/`
  and `candidate-result1-source-753c89f8c7934b22b4f823532fc3252a/`.
  Checkout-byte provenance proves 22 other physical hash differences are CRLF
  only; runtime is the sole semantic product difference.
- Five-band measurements: all 25 executions/readbacks pass with original source
  unchanged and all owned targets/sidecars removed. Prefix
  `measurements/result1-dadc1fef-20260929-153840-0bb41f93`; small-file median
  3.358 s / 1.163 MiB/s, below the non-gating 1.6 MiB/s goal. PERFORMANCE records
  all bands and overlapping historical ranges. Independent closeout review passed
  with no findings across source, tests, documentation and raw evidence.

Retain failed setup receipts: sandbox token differs from getpass identity, so
ACL fixtures require native execution; repository-local pytest temporary roots
are correctly refused by tool workspace tests. The successful native-default
rerun resolves both environment issues without product/test changes.

## Preservation and next action

The task-created baseline checkout is
`C:/Users/Spectrum/.codex/worktrees/executor-simplification-baseline/NamiSync`
at `b1b58476`; keep it through task closeout. Do not alter the pre-existing
`b8baf42d` root-admission baseline checkout, original F: benchmark source,
historical failed/raw receipts or recovery bundle. All new evidence is ignored
under the task evidence root. Commit exact task
paths, run the official oracle gate, then start the recorded handle outcome.
