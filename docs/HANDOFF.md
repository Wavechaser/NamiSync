# Latest session — row fix and remaining idle measurements complete, 2026-11-11

The user authorized the small row-attachment fix and then the remaining idle
measurements. Resource measurements remain non-blocking under accepted SH-G-15.
M1_PLAN owns the decision. Resources03 remains raw FAIL/incomplete; no receipt
was rewritten and no full soak is requested.

## Delivered correction and verification

The prior `rail.js` unconditionally appended retained rows during render. A bounded
native probe on exact candidate `cfeac2d9` reproduces a lost Close click:
render between trusted mouse-down/up detaches and reattaches the same row,
blurs the button and suppresses click. Both no-render controls invoke the
exact callback once. The original payload timeout lacks this trace, so its
cause remains unconfirmed.

Commit `1d936876` delivers the five-line correction, leaving ordered rows attached.
Its ordinary regression fails against the old code and passes after correction,
covering refresh/prepend and removal/reorder. A separate package extraction
with only the corrected rail asset overlaid passes trusted down/render/up,
exact callback count/identity and retained focus, with no row moves. This is a
native renderer diagnostic, not rebuilt-package acceptance. Close effects and
recovery are unchanged; no automatic mutation replay. Verification evidence:
`portable/rail-fix-20261110/` and `portable/rail-fix-native-20261110-02/`.
Resource handle ownership remains deferred diagnostic work.

Verification: the interfaces department passes 2,313 tests with the selected
Python 3.15.2 under Medium integrity and external temporary storage. The first
Low-token/repository-temp attempt is retained as invalid environment evidence;
its permission and custody-temp failures all clear in attempt02. Independent
review approves the product/test/docs delta and targeted measurement runner.

Package04 was built from clean detached `idle-followup-checkout` at `1d936876`.
ZIP SHA-256 `fca5c839cb9e4fb7a47e343656b08a9587961e2cdf2ccf8a920652875970311f`.
Independent comparison confirms exact native inputs/notices and byte-identical
embedded executable code; rail and attributable README/install/build metadata
are the only bundle differences. Preserve the first strict comparator receipt
alongside the corrected attribution and `package/artifact-comparison-review.md`.

Resources04 finished at 00:13 Shanghai time on 2026-11-11. Only the original
`idle-open-01` and `payload-01` profiles ran; both are valid and every applicable
predicate passes. The complete hour idle window had median 554.715 MiB and
reported slope +0.001 MiB/10 minutes; final closed memory was 551.262 MiB.
Payload peak was 442.828 MiB, final idle 404.104 MiB. All three task closes and
mirror checks pass; both apps exit 0 with empty owned Jobs. No run remains active.
Independent review is `acceptance/20261110-04/resources/review.md`; PERFORMANCE
owns the metrics and estimator. Preserve the raw partial-schedule FAIL for 15
deliberately absent profiles; do not relabel it a full 17-run pass or repeat the
soak. The Close/idle follow-up is complete. Final R5 reconciliation remains.

The runner and comparator remain ignored evidence tooling. No old checkout,
package environment, extraction, receipt or measuring-session process was
mutated. Retain both frozen checkouts and all task evidence for final accounting.

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
