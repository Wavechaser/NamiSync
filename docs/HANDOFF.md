# Latest session — policy-driven executor simplification

2026-09-29, `milestone1-adelbert`, starting clean at `9b694e0a`.
The equivalence baseline remains `b1b58476`. The user authorized results 1–3
and small atomic commits using execute-task. Direct writes remain deferred.

## Delivered and current outcome

Policy refinements are committed as `dadc1fe`; source-only consolidation is
`a6e2306`. The latter reuses fresh COPY/MOVE_UPDATE source fidelity, retains
retry and all target checks, removes source admissions with no later source
access, and retires retained-target refusal precedence.

The current native handle outcome carries an invocation-owned descriptor
through writing, metadata, flush, conditional publication and successful
post-publication observation. It releases before recording and on backup,
cleanup, operation retirement and invocation exit. Public contracts,
continuations, UPDATE recovery and retry namespace proofs remain unchanged.
The user approved finishing with already-granted handle rights when copied or
inherited ACLs would deny the old reopen/path publication.

Automatic approval review rejected target-fidelity consolidation even after
explicit user approval; that portion remains unapplied. No rejection was
bypassed. The smaller source-only outcome passed its gate and review.

## Verification

Evidence root: `build/executor-simplification-20260929/`.

- Native/ACL/retry focused run: 168 passed; final migrated control family:
  21 passed. Executor/workflow neighborhood: 1,479 passed in
  `handle-control-final-neighborhood.log`.
- Ordinary final: 5,633 passed, four unavailable symlink-privilege skips,
  34 deselected; `differential/result2-ordinary-final.log`. Imports: all 12 kept.
- Oracle unchanged: 30 scenarios × three, `differential/result2-oracle-initial.log`.
  Its baseline/pin remain those accepted in `a6e2306`.
- Differential: 67 groups, zero differences or oracle errors; capture
  `differential/runs/candidate-result2-handles-790e67a4c7e44f9bb3af36c594f6cfb9/`.
  Independent dependency audit matches current product/helper/adapter bytes.
  Guard scan: 70 rows, 391 effects, zero missing admissions.
- Native NTFS continuity, metadata-after-close, restrictive ACL, conditional
  rename and lifecycle witnesses pass. `handle-exfat-witness.json` proves
  K: exFAT rename/collision/replacement and close stability only; it avoids the
  separately excluded FileIdInfo defect and is not full executor acceptance.
- Retain failed ordinary/neighborhood and diagnostic receipts. Held-file
  pathname replacement/read blocked external mutation controls before their
  intended mutations. Seven narrowly scoped test sites exercise real fallback
  substitution/root-swap guards with all original assertions retained; native
  witnesses cover blocked attempts, truthful settlement and descriptor close.
  Source-open and after-close controls retain native behavior. No production
  changes were needed for this test migration.

Five-band measurement passed all 25 executions/readbacks; prefix
`measurements/result2-a6e23064-20260929-163929-812e188a`. Small-file median is
5.298 s / 0.737 MiB/s, slower than the preceding run; no throughput lift is
claimed. The bounded 20-sample ABBA diagnostic has pooled retained-handle
median 5.679 s versus fallback 5.909 s, with overlapping ranges. It does not
attribute the historical slowdown to handle selection. Prefix
`measurements/handle-abba-20260929-164758-75598d0c` retains all samples and
provenance; the earlier zero-sample driver failure is preserved.
Source/outcome, final test-migration and delivery-document independent reviews
have no findings. Supplemental import-origin and complete measurement audits
are retained beside the measurement receipts.

## Immediate continuation

The handle outcome is verified. Continue with the recorded planner-fidelity
outcome and independent verifier-leaf outcome after its atomic integration.
Read-only design refreshed native/runtime handle seams; bind it to the
integrated commit before implementation. UPDATE backup repair/restoration and
failed DELETE restoration must use the full admitted target observation while
retaining strict recovery comparisons. M1_PLAN owns the finite population.

Keep the task-created baseline checkout at
`C:/Users/Spectrum/.codex/worktrees/executor-simplification-baseline/NamiSync`
through task closeout. Preserve the pre-existing `b8baf42d` root-admission
baseline, original F: benchmark source, historical evidence and recovery bundle.
All new evidence is ignored under the task evidence root. Native ACL gates use
the actual Windows user and standard external pytest temp; sandbox identity and
repository-local tool fixtures are not valid substitutes.
