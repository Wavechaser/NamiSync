# Latest session — post-M1-8 ablation study

2026-09-25: the user requested a read-only, repository-wide ablation study after
M1-7 and M1-8, then asked for it to be recorded under `docs/` and committed.
Baseline `549f3b4` on `milestone1`. The prior session's MOVE-1 handoff remains in
that commit's `docs/HANDOFF.md`.

Delivered: [POST_M1_8_ABLATION](POST_M1_8_ABLATION.md), a README index entry
and a CHANGELOG task. No product, test, tool, evidence-policy or delivery-register
change was made; M1_PLAN scope is unchanged. The study proposes structural
changes S1–S5, local reductions L1–L9, test changes T1–T3, evidence change E1 and
workflow changes W1–W4. Each needs a user decision (D1–D7) and, per AGENTS, a
closed register before implementation.

Verification: study claims were traced by nine read-only analysts and headline
claims re-verified in code. In a disposable clone of `549f3b4` with Node v22.18.0
through `NAMISYNC_TEST_NODE`, the ordinary suite gave 5,403 passed, 5 skipped and
14 environmental failures (12 `test_tools_gui.py` cases need a `.venv` inside the
checkout; two `test_plan_review_scale.py` cases call bare `node`). Comment-only
edits and three behavior-preserving refactors added only two failures, both
prescriptive `test_design_tokens.py` checks. This commit is documentation-only:
`git diff --check` and local documentation-link checks passed; no product tests
were run against the live checkout.

Operational context: this machine has no project Node on `PATH`; the run used a
locally installed Adobe Creative Cloud Node binary only for the disposable clone.
Evidence and scripts are in ignored `build/post-m1-8-ablation-20260925/`; the
clone and its worktrees were deleted. Page reload being unreachable in the
shipped app (S1) is established from source, not yet from a manual check on an
installed build. Pending GUI work, M1-9 onward and the deferred M1-7 study remain
outside this session.
