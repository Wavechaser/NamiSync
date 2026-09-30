# Latest session — held-root path composition

2026-09-30, `milestone1-adelbert`, result-6 candidate based on `d43f832`.
Active scope is results 5–7 with small atomic commits and measurements; direct
writes/result 8 remain excluded. Result 5 is committed as `d43f832` after the
user's explicit recorder authorization; the directive commit is `8b2b00e`.

## Current outcome

Result 6 replaces native conversion caches with one validated prefix per admitted
held root, composes descendant paths and removes conversion-only precedence
probes. Per-access held attributes, descendant guards, fallback validation and
volume semantics remain. ASCII-drive and trailing-separator parity corrections
were made before final acceptance. Cache-mechanism tests were replaced with
parity/refusal/lifetime/fallback tests; no required production guard was retired.

Final verification: 343 native/runtime tests and 5,711 ordinary tests passed;
four existing capability skips and 34 deselected. Ordinary coverage includes the
executor department. All 12 imports, unchanged 30x3 settlement oracle and
70-row/391-effect guard scan pass. The saved 67-group differential has zero
differences, and current source/helper hashes match its receipt. Fresh independent
review covers source, test migrations and evidence before the atomic commit.

Evidence root: `build/executor-simplification-20260929/`. Logs use
`differential/result6-*`; final focused receipt is
`result6-native-runtime-eligibility-final.log`. Differential capture:
`runs/candidate-result6-paths-a541008d975c4abcb81e1c8d035c71ab/` under that directory.
Measurement prefix: `measurements/result6-d43f8324-20260930-133019-7ae09623`.
All 25 executions/readbacks passed with zero reservations, unchanged source and
dependencies and owned-target cleanup. Medians: 3.211 / 1.682 / 0.348 / 0.302 /
1.999 s; predecessor ranges overlap. PERFORMANCE owns the table and limits.

## Next and preservation

Commit result 6, then implement result 7: remove method-identity dispatch and
migrate affected guard/volume-probe test overrides to native primitives. The
read-only design inspected base `d43f832` and native SHA-256
`c40c0bb00d5e9f8b2b144ac6dc8aab9df5e9dcdef535fb67e0bf086e8f886702`;
refresh against integrated result 6 before editing. Saved differential driver
and helper bytes stay unchanged; classify any declared custom-dispatch changes.

The first sandbox setup failed on temp ACLs; actual-user/default-temp baseline
passed. The exact task-owned sandbox fixture tree was restored to inherited ACLs
and removed (39 entries), retaining `result6-fixture-*` receipts. A development
spy failure log was accidentally overwritten by its retry; the reconstruction is
explicitly labeled in `result6-development-note.txt`. Final distinct acceptance
logs are intact. Future native tests must use actual user/default temp.

Recovery `9f01bfd9` remains on `codex/wip-20260930-1246-executor-version` pending
final integrated accounting; it was rebuilt into result 5, never merged. No
worktree was created. Original F: source, old evidence and unrelated `b8baf42d`
worktree remain protected. No direct-write implementation or device sweep began.
