# Latest session handoff

## M1-7 full acceptance and closure (2026-09-16)

The user authorized one full measurement run on P8 (`3c3bbbc`), followed by
M1-7 closure if it passed, with multiple coherent integration commits rather
than a single squash. Product and measurement code stayed unchanged.

P9 passed all 35 readiness cases in 15 children and all 35 fixed quantitative
criteria across 175 fresh children / 775 samples, without retries. Independent
terminal, collection, process identity and source/installed/wheel/runtime audit
passed. Changed-sort p95s are 0.756–1.109 s (largest max 1.192 s); review memory
is 280,768,512 bytes / 267.762 MiB; execution admission receipt is 54.6 ms p95,
55.4 ms max. The original 1.5/3 s, 320 MiB and 100/250 ms criteria are unchanged.
Receipt timing still follows actual admission. Memory does not measure the
shared index's extended paused-execution lifetime, documented in ARCHITECTURE.

Evidence root: `build/m1-7/evidence/p9-full-20260916/`. It includes fresh
authority, readiness, all raw child receipts, incremental collection indexes,
terminal measurements, `evidence-audit.json`, and supplemental before/after
core execution identities. Canonical compact authority/measurement artifacts
are updated; previous bytes are preserved in the evidence directory and Git.
No legacy contract or historical legacy artifact is changed. M1_PLAN records
artifact hashes, supplemental binding, scope and integration requirements.

Prior unchanged P8 checks passed: 5,157 ordinary tests, 259 focused checkpoint/
resume/post-execution tests, 12 import contracts and the installed Plan flow.
Final new-artifact/scale validation passes 55 tests (28.62 s); the ordinary suite
passes 5,158 tests with four platform skips and 30 headed deselections (262.71 s).
Independent documentation and reconstructed endpoint reviews pass. The P8 import
and installed Plan results remain applicable because product/test code is
unchanged. Clean committed-source validation, supplemental core physical/HEAD
identity and exact product/test accounting passed on the accepted recovery
revision `ba31c1e`; the same checks bind the final reconstructed series.

M1-7 is complete. Integration into `milestone1` uses six reconstructed outcomes:
Plan/confirmation and framework
readiness; covered windows and compact Plan scale; review/selection retention;
digest reuse; shared structure; accepted evidence/closure. The final product/test
tree equals P8 except the two accepted artifacts. Original recovery commits,
including `cf5a00b`, remain unchanged under archive tag
`codex/m1-7-recovery-20260916` and verified `m1-7-recovery.bundle` in the evidence
root. The recovery and temporary integration branches are pruned only after
verified integration. `integration-receipt.json` records both tips, exact tree
accounting, bundle identity and cleanup; it is the operational Git receipt.

Reviewed reconstructed commits: `ae3daf6` (foundation/framework), `8ffbd3a`
(compact Plan), `5c31894` (retention), `ef2308a` (digest), `ea5f997` (structure).
Their final tree is exactly `3c3bbbc`; `d1ce79d` carries accepted evidence.
This final documentation record follows the verified fast-forward and cleanup;
the current checkout is `milestone1`. No changes were pushed.

Stop on `milestone1` for recap and GUI review. No M1-8, DOC-2, push, PR
or release work is authorized.
