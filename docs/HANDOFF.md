# Latest session — Plan limits and copy-only throughput, 2026-11-06

Base `8628a5b9`, branch `milestone1`. Preflight now charges reviewed operations
once. Every derived source, target, prior path and parent remains scoped to
that Plan. The original dry run now saves 100,000 copies and 1,000 directories
with 202,000 observations and can proceed to explicit review. Its empty target
and private databases were removed. The core, preflight and workflows gates
passed 2,191 tests with one skip. Receipts in `build/coverage-study-20261106/`:
`refusal.json`, `fixed-plan.json` and `fixed-plan-tests.xml`.

The page retains the terminal refusal on release and reselection. A focused
WebView2 journey exercised a real refusal on a small fixture, with no target
changes and normal exit. All 65 frontend checks passed. Evidence:
`build/refusal-ui-20261106/runs/refusal/verified.json`. The bounded
above-envelope policy and matched copy-only timings follow.
