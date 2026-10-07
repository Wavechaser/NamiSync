# Latest session — bounded bridge counter delivered; investigation next

2026-10-07, milestone1, from 706be4b. User scope is #1 implementation and
#2–5 investigation only. M1_PLAN owns BC1a/BC1b and BC2–5; no further capture,
DTO, DOM or prefetch optimization is approved. Prior GUI-C1–C5 is complete;
its original evidence/accounting remains in build/gui-inventory-refinement-20261005/.

BC1a (806df04) removes hot observer work. BC1b uses 4,096-character JSON/UTF-8
chunks with scalar fallback outside the encoding exception handler, preserving
upfront quotes, exact bytes, invalid-Unicode/overflow precedence, partial budget,
budget=None validation, occurrence counting and detached hostile-source custody.
The only product change is bridge.py. The observer control was migrated to
permit legitimate product string encoding, while still forbidding whole-response
or extra observer serialization. No response limit or wire contract changed.

Evidence is build/bridge-counter-study-20261007/. BC1a has 33 focused and 398
tools passes. BC1b: 587 composition, 191 post-migration focused, 5,982 ordinary
(four privilege skips), 12 import contracts and six installed transport passes.
Retain the first ordinary test-control failure and all earlier sandbox/fixture
receipts; no persistent policy changed. Independent reviews inspect source,
controls, custody and provenance. Final identities belong in integration.md.

Corrected baseline/candidate matrices each have six fresh children/96 gesture
observations, with same collector, pins, profile and restored installed assets.
Jump capture Plan 18.505→12.477 ms, Inventory17.070→13.568; first coverage
57.6→50.2 / 57.3→56.3 ms. Burst coverage120.6→120.6 /144.7→128.0 ms.
Plan burst scheduling now dispatches more intermediate reads; both components
retain maximum one concurrent read. No general latency guarantee. PERFORMANCE
and comparison-summary.json retain ranges, byte identity and caveats. Original
C5 hot-observer timings cannot serve as this optimization's baseline.

Next: BC2–5 method in PERFORMANCE is declared before collection. Three ignored
bc25 helpers and run-bc25.ps1 are source-reviewed; native diagnostics restore
assets, retain actual trajectory/ownership/row coverage and isolate forced
geometry probes from steady scrolling. Run capture replay/field accounting,
then separate installed DOM/steady diagnostics (three children per component).
No product fixes. Record results and recommendations for the user to decide.

Both fresh installations, baseline/candidate raw receipts, source manifests,
profile and failures are retained. Tests/profiling never overlap headline timing.
Actual native/broad runs need require_escalated (actual Windows user), preserving
foreground guards. No active test/measurement process at this checkpoint.
No push, PR, worktree or unrelated changes.
