# Latest session — WCG shadow halo isolation and GUI-W1 mitigation

The deferred dark flyout halo (BUGS, desktop material composition) is a
Windows DWM Advanced Color defect in composing per-pixel-alpha window content.
GUI-D8–D10 evidence and reproducers are in `build/gui-tuning/halo-10bit/`
(its AGENTS.md maps scripts, runs and the D5/D6→D8/D9 renumbering). Key
method: 8-bit GDI screenshots show DWM's exact legacy composition and cannot
see the halo; `transfer_capture.py --fp16 0` grabs scRGB FP16 through ffmpeg
`ddagrab` and does. `native_probe.py --backdrop none --grid` reproduces it
without WebView2 or Mica. scRGB-linear Chromium output was tried and rejected.

GUI-W1 (M1_PLAN) mitigates, not fixes: `appearance.py` reads the window
display's Advanced Color state through DisplayConfig, refreshes it on display
settings, monitor changes and activation without reapplying material, and
publishes `advancedColor` in `namisync.appearance.v3`; `components.css` drops
dark flyout shadows under `data-advanced-color="true"`, mirroring the HDR rule.
The bug entry stays DEFERRED.

Verification: 165 focused appearance/frontend/token checks; all 4 installed
gallery headed tests on this LG WCG display, whose evidence records
`advanced_color: true`, dark popup shadow `none` and light shadow retained;
a live monitor move flipped the page flag LG true → Dell false → LG true
(`transfer-w1-dataset/`); 1878 interfaces-department passes; 12 import
contracts. Two `test_plan_review_scale.py` probes call bare `node` from PATH
rather than `NAMISYNC_TEST_NODE`, so the department needs the codex Node
runtime on PATH as well
(`C:\Users\Spectrum\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin`).
That harness inconsistency is pre-existing and not fixed here.

Not verified: an actual HDR session and live ACM toggling with the app open
(activation refresh is the fallback if Windows sends no display-change event).
Filter/Search, theme changes, M1-7 reduction-study resumption, M1-9, push and
PR remain excluded; DOC-2 remains pending.
