# Latest session — policy-driven executor and verifier simplification

2026-09-29, `milestone1-adelbert`, starting clean at `9b694e0a`.
The equivalence baseline remains `b1b58476`. The user authorized results 1–3
and small atomic commits using execute-task. Direct writes remain deferred.

## Delivered and current outcome

Policy refinements are committed as `dadc1fe`; source-only consolidation is
`a6e2306`. The latter reuses fresh COPY/MOVE_UPDATE source fidelity, retains
retry and all target checks, removes source admissions with no later source
access, and retires retained-target refusal precedence.

Handle outcome `0d7dd6b` carries an invocation-owned descriptor
through writing, metadata, flush, conditional publication and successful
post-publication observation. It releases before recording and on backup,
cleanup, operation retirement and invocation exit. Public contracts,
continuations, UPDATE recovery and retry namespace proofs remain unchanged.
The user approved finishing with already-granted handle rights when copied or
inherited ACLs would deny the old reopen/path publication.

Automatic approval review rejected target-fidelity consolidation even after
explicit user approval; that portion remains unapplied. No rejection was
bypassed. The smaller source-only outcome passed its gate and review.

## Planner-fidelity outcome — `84ce0fb`

The shared planning predicate now bounds admission metadata to managed attributes
and MOVE/MOVE_UPDATE link eligibility. Full observations still own publication,
backup, recovery, restoration, optimistic DB concurrency and integrity checks.
Identity semantics and wire shapes remain unchanged. Native weak-profile RECASE
and admitted-metadata restoration witnesses cover the consumer migration.

Current verification: 904 focused tests (one existing skip), 5,702 ordinary
tests (four existing symlink-privilege skips, 34 deselected), all 12 import
contracts, unchanged 30×3 oracle, 67 differential groups with zero differences,
and 70-row/391-effect admission scan with zero missing admissions. Receipts are
`differential/result3a-*.log`; the differential capture is
`differential/runs/candidate-result3a-fidelity-563226ff78a748799e044bd17741fb48/`.
The optional AST audit failed and is not gate evidence; its attempts are retained.

All 25 five-band executions/readbacks passed under prefix
`measurements/result3a-0d7dd6bf-20260929-173343-1dcc369e`. Medians are
6.489/3.503/0.708/0.354/2.482 s from smallest to largest band. Small-file
throughput is 0.602 MiB/s; no throughput lift is established. PERFORMANCE owns
the comparison and exact evidence limits.

Evidence root: `build/executor-simplification-20260929/`. Earlier outcome gates,
measurements and review dispositions remain in M1_PLAN, PERFORMANCE and its
README. The 70-row oracle pin remains the one accepted in `a6e2306`.
Retained-handle external-mutation controls use seven narrowly scoped fallback
sites with their original assertions; native blocked-attempt witnesses remain.
The exFAT witness proves low-level rename/close stability, not full executor
acceptance. Preserve failed test/diagnostic receipts alongside successful runs.

## Final verifier outcome

The first three code outcomes are integrated and independently reviewed.
The final verifier outcome removes only the duplicate placeholder classifier and
its unused import. The user chose preserving the walk/result classes: moving
the leaf check saved no query and changed native junction results. Existing
verifier/core seams were unchanged between design and integrated `84ce0fb`.
Focused tests passed 239; the verifier/database/workflow neighborhood passed
1,465. The initial unknown-department selection error ran no tests and its
receipt is retained. The final ordinary suite passed 5,702 with four skips and
34 deselected; imports, unchanged oracle, admission scan and all 67 differential
groups pass. A README review correction limits the incidental-metadata claim
to plan admission; all 85 checks in the five ordinary package-consumer modules
pass after that correction. All 25 final measurement/readback samples pass;
prefix `measurements/result3b-84ce0fb2-20260929-175649-85162057` retains exact
provenance and owned cleanup. Small-file throughput is 0.628 MiB/s and the
4 GiB band is 1,765.673 MiB/s. Both goals remain unmet; no lift is established.
Independent final review passed. No tests or safeguards were added
or removed by this verifier outcome. Final receipts use `differential/result3b-*`;
the 67-group capture is
`differential/runs/candidate-result3b-verifier-05d1c814c4754f52a91799bd755e0d9a/`.
The authorized results 1–3 are closed with the target-consolidation block and
approved verifier disposition recorded above. No direct-write work was started.

## Deferred findings and preservation

Native NORMAL→ARCHIVE own-effect failures reproduce in starting `b1b58476` and
the candidate across five rename/hardlink cases. This pre-existing mechanism is
deferred in BUGS/M1_PLAN; its `differential/result3a-archive-*.json` receipts
preserve actual effects and settlement. Do not mask strict recovery comparisons
to make these cases pass as part of planner-fidelity work.

The clean task-created baseline checkout at
`C:/Users/Spectrum/.codex/worktrees/executor-simplification-baseline/NamiSync`
was verified at `b1b58476` and archived through the app after the final capture
and measurement. The archive attachment is recoverable. Preserve the pre-existing `b8baf42d` root-admission
baseline, original F: benchmark source, historical evidence and recovery bundle.
All new evidence is ignored under the task evidence root. Native ACL gates use
the actual Windows user and standard external pytest temp; sandbox identity and
repository-local tool fixtures are not valid substitutes.
