# Latest session handoff

## R7-1 consolidation (2026-09-17)

Startup committed as ee8d861 on milestone1 after clean d91871f baseline.
User authorized R7-1–R7-8 and R7-G under execute-task. The
[ablation register](M1_7_ABLATION_STUDY.md) owns the finite scope and gates;
M1_PLAN is the parent. Deferred candidates/F1 hardening and push/PR stay excluded.

R7-1 separates frozen synthetic expectations from actual generator observations
in test_plan_review_scale.py; production, generator, validator and historical
artifact bytes are unchanged. PRESENTATION records the provider distinction.
S passed 55 with one historical-artifact skip; I passed 1,673 with one skip
and 3,519 deselected. The skip lacks NAMISYNC_M1_7_READINESS_PATH and is not Q.
The initial task-owned TEMP workaround triggered custody's source-tree cache
refusal; normal external TEMP with escalated test execution passed. Use external
TEMP for broad gates; do not change custody guards to accommodate sandbox paths.

Copied-source population/order/retained descriptor and maximum-only validator
faults each fail causal assertions; harmless metadata passes. The 30-function
synthetic cohort passes all 41 cases with both generator symbols trapped.
Evidence: build/m1-7-ablation/implementation/r7-1/manifest.md. Initial in-memory
controls are supplementary; the later copied-source controls satisfy the gate.
Fresh independent review approved the actual diff and corrected evidence.
Documentation link/diff checks pass. R7-1 is the commit containing this handoff:
`test(presentation): Separate synthetic and live scale fixtures`.

Measurement policy: affected Q-local Tier 1 guards per checkpoint, one full
Q-final at R7-G. Local passes do not renew full acceptance or pool children.
Keep budgets, full validator and P9/legacy bytes unchanged. R7-1 has no timed
code changes. Next: verify R7-1 committed-source identity, then refresh and freeze R7-2 scope
and baseline. Read-only R7-2 design is in the startup evidence directory;
only memory/staging sampling includes its comparator path, not cold-build or
warm-sort timers. Baseline P passed 166 at unchanged product bytes.

Preserve original study/E1/E2 under build/m1-7-ablation/, P9 under
build/m1-7/evidence/p9-full-20260916/, and recovery archive/bundle in M1_PLAN.
All task-owned controls remain under ignored implementation/checkpoint roots.
Apply AGENTS mandatory stops, recurrence, and recovery; latent defects report-only.
