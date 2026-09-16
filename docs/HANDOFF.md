# Latest session handoff

## M1-7 ablation study (2026-09-16)

The user requested a coarse-to-fine ablation study of delivered commits
`ae3daf6` through `5986c57`, including an independent single Opus 5 xhigh review.
The checkout remains on `milestone1` at `5986c57`. Production and test paths
are unchanged; only study/report/index/changelog/handoff documentation is edited.
No commit, push, PR, M1-8 work or product implementation was performed.

[M1_7_ABLATION_STUDY.md](M1_7_ABLATION_STUDY.md) is the final report.
[M1_PLAN.md](M1_PLAN.md#post-delivery-ablation-study-2026-09-16) closes AB7-1–AB7-4.
The report contains twelve candidates with source evidence, retained guarantees,
falsifying gates and sequencing. Recommendations are not implementation authority.

Strong candidates consolidate independent-validator receipt checks, producer
publication bookkeeping, browser retries and selection admission; separate
synthetic validator fixtures from live scale construction; remove test ordinal/
source-count coupling and unused mechanisms; and avoid four repeated safety
derivations on a successful selection mutation. Public preview compatibility and
workflow authority must survive. A larger selection-overlay representation needs
hotspot evidence; legacy-reader and diagnostic-tracer retirements need explicit
dispositions. Do not merge all recommendations into another oversized checkpoint.

E1 in a disposable copy: 33 focused projection/review tests passed before and
after a canonical-comparator simplification; intentional reverse ordering failed
the retained nonlexical-order assertion. E2: five synthetic validator controls
passed before and after substituting frozen manifests with live generation
forced to raise; intentionally removing maximum-budget rejection failed the
existing maximum-only control. E2 is a cohort-only diagnostic patch, not an
integration-ready replacement for shared live-fixture helpers. Both copies were
removed after their absolute paths were checked. No full ordinary/headed suite
or 175-child scale run was repeated; no performance acceptance is claimed.

Two Codex sidecars reviewed measurement and frontend/harness families, followed
by adversarial checks. Claude used Opus 5 xhigh in session
`bfd6b79e-d74d-4714-a0cc-38bdafe5b5e2`, then resumed that exact session for a
targeted challenge. Both invocations report zero Claude subagents. The reviewer
accepted corrections to census, map copying, membership cost, public DTO and
constructor-validation contracts, fake-DOM assumptions and rerun-policy claims.
The final report records each disposition and separate per-model usage; total
CLI-reported cost is $9.483037, including $0.001508 auxiliary Haiku usage.

Evidence: ignored `build/m1-7-ablation/` holds the inventory, prompts, raw JSON,
review tool audit, original-state preservation receipt, experiment manifests,
scripts, exact patches and six control/ablation/fault logs. Review-start tracked
diff/status stayed unchanged through Claude's work. Documentation/link/diff
checks and product/test identity against `5986c57` close this delivery.

M1-7 acceptance remains the prior P9 result at
`build/m1-7/evidence/p9-full-20260916/`, with canonical committed artifacts and
supplemental core binding recorded in M1_PLAN. This study neither replaces nor
revalidates those measurements. Recovery ancestry remains under
`codex/m1-7-recovery-20260916` and its verified bundle. Next action is discussion
and selection of bounded simplification scope, not automatic implementation.
