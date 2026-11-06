# Latest session — Driven resource pilot; renderer defect logged, 2026-11-06

Branch `milestone1`, starting from `bde11e88`. Product source is unchanged.
The user chose **log it, stop for now** after the first workload pilots found a
renderer memory defect. Do not resume the resource baseline until it is fixed.

## What changed

- Control approach settled: the unchanged build-d package runs with only
  `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS` adding a loopback
  `--remote-debugging-port`. Trusted CDP mouse/text input drives the page; no
  window focus, UIA or native typing is needed. The previous session's
  activation and typing failures do not recur.
- The user directed that SH-G-15 be judged on measured behavior rather than a
  predeclared budget/validator apparatus. M1_PLAN records this.
- New, **uncommitted** drivers: `tools/performance/_cdp.py`, `resources.py`
  (collector: frozen schedule, registry-first fixtures, mirror/`.synctrash`
  checks, `cleanup`) and `validate_resources.py` (window statistics and
  yardsticks), plus `tests/test_resource_acceptance.py` registered in the
  tools department. Decide whether to keep their acceptance framing before
  committing them; the docs change only records observations.
- BUGS gains two OPEN entries: SEVERE render allocation outpacing collection
  (Interfaces › Live execution rendering) and MODERATE dead-page shutdown
  dependency (Desktop bridge and native-owner lifecycle). PERFORMANCE records
  the pilot table and method; CHANGELOG extends the 2026-11-06 task.

## Findings

Execute with verify on grows renderer memory ~70 MiB/s: 1,000 × 4 KiB files
peak 3,029 MiB whole-app (2,668 renderer), and stay ~2.3 GiB after every task
closes. A 10,100-item plan reached 7.8 GiB, crashed with WebView2's Out of
Memory page, reloaded and died again. Diagnosis shows collectable garbage
(JS heap 914 MiB → 2.9 MiB after one forced GC; DOM 61k → 5.7k nodes) and CPU in
layout/style, `getBoundingClientRect` (`table_columns.js` `refreshResizers`),
`cloneJsonValue` and Plan render. The page paces execution: 10k tiny files took
5 minutes. Per-event full-window redraw is the leading hypothesis, unconfirmed.
After renderer death, window close failed twice with `_DesktopQuiescenceError`;
the harness ended the Job at 130 seconds. That sync had already completed
durably (10,100 succeeded, verify, recording/audit ok) and the target mirrors
exactly. Also seen: while planning, the task card briefly shows "Completed".

Host memory stayed 93–178 MiB. The earlier startup baseline (settled ~358 MiB)
is unaffected.

## Verification

`tests/test_resource_acceptance.py` plus department policy: 22 passed. Pilot
soak (3 cycles), 50-file and update-cycle explorations: mirror and trash
counts correct, normal exit 0 and empty Jobs. No run synced from the supplied
corpus; the collector only recorded its metadata.

## Resumption

1. Fix the renderer churn (frontend/bridge owners), then reuse
   `build/resource-baseline-20261106/diag.py` on 1,000 and 10,000 files as the
   before/after check, and fix or adjudicate the shutdown dependency.
2. Rebuild a package and rerun the full schedule: `python -m
   tools.performance.resources collect --archive ... --out NEW_DIR --corpus
   F:\NamiSyncExecutorBenchSource --source-parent F:\ --target-parent
   H:\test_dir`, then `python -m tools.performance.validate_resources NEW_DIR`.
   About 4.5 hours; run nothing else meanwhile.

Evidence: `build/resource-baseline-20261106/` (`runs/explore-0*`, `pilot/`,
`diag/` with CPU profile and heap snapshot). Registered pilot fixtures remain
under `F:\NamiSync-resource-*` and `H:\test_dir\NamiSync-resource-*`, listed in
`pilot/fixtures.jsonl`; remove with `resources cleanup --out
build\resource-baseline-20261106\pilot` once no longer needed. The earlier
exploration pair `NamiSync-resource-explore-7dc1e22b` (F: and H:\test_dir) is
recorded in `build/resource-baseline-20261106/fixtures.jsonl` and must be
removed by hand.
Prior study evidence remains in `build/resource-study-20261106/`.

R2 (native-input provenance, notices, guide integration), R3 acceptance, R4
candidate checks and R5 handoff remain open. No publication.
