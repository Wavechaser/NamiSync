# Latest session — Close-input diagnosis and packaged High pass, 2026-11-10

The user requested a quick Close-timeout investigation, confirmed resource
measurements are non-blocking under accepted SH-G-15, and was present for UAC.
No further soak ran. M1_PLAN owns the decision. Resources03 remains raw
FAIL/incomplete, including missing open-idle coverage; no receipt was rewritten.

## Close finding and next step

Shipped `rail.js` unconditionally appends retained rows during render. A bounded
native probe on exact candidate `cfeac2d9` reproduces a lost Close click:
render between trusted mouse-down/up detaches and reattaches the same row,
blurs the button and suppresses click. Both no-render controls invoke the
exact callback once. The original payload timeout lacks this trace, so its
cause remains unconfirmed. No product code changed.

Recommended correction: ordered row reconciliation that leaves correctly
positioned rows attached. Verify trusted down/render/up, callback identity/count
and ordering/insertion/removal. Preserve Close effects/recovery; no automatic
mutation replay. This session delivered investigation, not implementation or
R5 closure. Resource handle ownership remains deferred diagnostic work.

Evidence root `build/m1-release-repair-20261110/portable/`:
- `rail-click-probe.py`, `rail-click-probe.js` and
  `rail-click-probe-20261110-02/probe-result.json`, SHA-256
  `dfd305426ea07080a3d0973e11564a39ba903f61c9b92511c3ccab0a1e00e142`.
  Attempt01 refused the Low-token harness before GUI launch. Attempt02 used
  Medium integrity. Its host exited 0; two WebView2 children exceeded the grace
  period and were contained by the owned Job. Subsequent checks found all owned
  PIDs gone. Do not call this an empty-Job graceful-close witness.
- `rail-click-review.md` holds independent diagnostic review.
- Earlier `payload-pilot-{01,02}/` passed without reproducing the original
  timeout; preserve those and the original failed payload receipt unchanged.

## Packaged High and retained release evidence

`high-20261110-02/receipt.json` and `high-uac-20261110-02.json` pass actual UAC
and elevated refusal. The exact GUI ran with elevation 1 / High SID 12288,
showed the expected refusal, created no app data, exited 1 and left an empty
owned Job. `high-review-02.md` independently verifies the result. Canceled
attempt01 remains; unchanged bytes need no further UAC request.

Candidate `cfeac2d95a6db83107854d17d9e6c4e9a774b77e` retains complete release
6,575 passes/four unchanged capability skips, 12 imports, 30 × 3 settlement,
R3 timing, package census and Medium journey passes. Portable ZIP SHA-256:
`a840c9b0fedc31a442e677cb81c7281d5901ed9eafa1e1d25f31c991d9ceff5a`.
Evidence lives under `acceptance/20261110-03/`; R3 receipts are committed.

Frozen `acceptance-checkout` remains on `codex/release-repair-authority-v2`
at `cfeac2d9` with its private selected runtime. Preserve authority introduction
`eb98c95f` in ancestry; no rebase/cherry-pick. Root `.venv` and global Python
are untouched. Keep recovery `ed18ad3e` on
`codex/wip-20261110-release-repair` for final accounting; it was rebuilt, never
merged. Retain old R4 `3ece185f`, `build/m1-r4-20261109/` and old R5 delivery
under `build/m1-r5-20261110/`. No cleanup, upload, tag, push or external delivery
occurred. Final R5 review, immutable tester handoff and external
delivery/Microsoft agreement decision remain open.
