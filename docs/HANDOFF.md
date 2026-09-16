# Latest session handoff

## R7 consolidation through R7-2 (2026-09-17)

Authorized batch: R7-1–R7-8 and R7-G under execute-task; deferred items/F1
hardening, push and PR excluded. Parent M1_PLAN and detailed
[ablation register](M1_7_ABLATION_STUDY.md) own scope/gates.
Startup baseline/policy: ee8d861. R7-1: efb5dc7, synthetic/live fixture split,
S55/I1673 (one historical-artifact skip each), 41-case generation-trap cohort
and copied-source faults passed. Clean committed identity verified.

R7-2 is the commit containing this handoff, titled
`refactor(workflows): Simplify canonical Plan ordering`. It replaces the sole
canonical comparator with the direct path/node key and removes orphan branches,
helper and import. The separate real-sort implementation is unchanged. Three
new edge cases pass against old source too; candidate four-node control passes,
and a copied reversed-key mutant fails the intended order assertion.
P169, WI2480/1 historical-artifact skip, L12 contracts pass. Fresh independent
review approved the actual diff, local measurement provenance and controls.

Q-local memory/staging: baseline five-child max 278835200 bytes, range 2371584;
candidate max 285605888 bytes, range 2609152; fixed budget 335544320 bytes.
Candidate maximum increased; no memory improvement claimed. Both phase authority
before/after, source/wheel/install/runtime/profile and supplemental execution
bindings pass. Raw evidence and exact commands live under
build/m1-7-ablation/implementation/r7-2/. Native freeze required desktop-capable
execution; pip installation used no cache after a permission failure. A task
checker hash-case correction revalidated the same baseline receipts, without
rerunning children. These were setup/checker issues, not product regressions.

Measurement policy remains affected Tier 1 local guards per checkpoint and one
full Q-final at R7-G. Local passes do not renew acceptance, pool children or
rewrite P9/legacy artifacts. Use normal external TEMP with escalated verification
when needed; repository-local TEMP trips custody's intentional cache guard.
Historical-artifact skip lacks NAMISYNC_M1_7_READINESS_PATH and is never Q.

Next: verify R7-2 committed-source hashes, refresh R7-3 read-only expansion
against its canonical constructor seam, then remove only unused replace_projection
and migrate its four test consumers. No benchmark calls that route, so predeclare
no Q-local timed IDs if the deletion stays narrow; H remains required. Draft
is under implementation/startup/r7-3-expansion.md. Continue authorized batch;
AGENTS stops/recurrence/recovery remain binding, latent defects report-only.
Preserve all original/P9 evidence and task-owned control copies through closeout.
