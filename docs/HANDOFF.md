# Latest session — bridge counter study

2026-10-07, milestone1, from 706be4b. The user authorizes #1 bounded bulk
counter implementation and #2–5 investigation only; M1_PLAN owns BC1a/BC1b
and BC2–5 scope. No further capture, DTO, DOM or prefetch optimization is
approved. Prior GUI-C1–C5 is complete; its evidence and recovery accounting
remain in build/gui-inventory-refinement-20261005/integration.md.

BC1a removes per-character budget observer overhead from the loading collector.
It reads actual outer-capture budget consumption on success; failed captures
publish no partial byte metric. Product code remains unchanged. Independent
fresh review found no actionable issue. Controls pass 33; the actual-user tools
gate bc1-observer-tools-01 passes 398 with three skips. Preserve earlier invalid
ceiling controls and sandbox policy failures; the process-policy variation is
supporting evidence only, not the closure gate. No persistent policy changed.

Evidence and unique helper/run conventions live in
build/bridge-counter-study-20261007/. Fresh bc1-install-baseline-01 binds the
unchanged product and exact prior runtime pins. The fresh host profile retains
unknown power/unrelated workload. Next: corrected-observer installed probes and
six-child baseline, then BC1b product edits, focused composition/ordinary/import
checks, independent review and identical installed comparison. Do not compare
old C5 timing directly with the new counter: its hot observer biased capture.
Do not run suites/profiling alongside headline timing or edit frozen inputs.

BC1b design evidence compares bounded 4,096-character encoding with the old
walk; preserve upfront quote charge and scalar fallback outside the encoder
exception handler for unchanged failure ordering/context and remaining budget.
Raw design microbenchmarks are diagnostic, not installed speed acceptance.
Actual native/broad gates need require_escalated to run as the actual Windows
user; sandbox environment labels can be misleading. Keep native foreground
guards. No push, PR, worktree or unrelated changes.
