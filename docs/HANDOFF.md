# Latest session — GUI alignment

2026-10-05 on `milestone1`, base `999a568`. The user ratified the seven-point
GUI alignment register in [M1_PLAN](M1_PLAN.md). A1–A5 are active, in order;
execution-to-Verify navigation (A6) is deferred to M1-10, and all previous-
location/rename redesign (A7) is deferred to a focused session. Standalone
Verify stays on Integrity with Sync disabled. No A7 presentation-boundary
exception was approved.

## Current checkpoint

A1 corrects move-reveal recovery in `assets/app.js`. A still-current rejected
or revision-mismatched follow-up window retains the last coherent display and
offers Refresh. A coherent conflict scrolls to the loaded offset. Stale
task/navigation replies remain inert; no retries or bridge changes were added.
Direct shell/renderer probes cover failure recovery and offset-zero scrolling.

Evidence lives in `build/gui-alignment-20261005/`, whose README defines naming
and retention. The red probe fails the intended missing-refresh assertion;
seven focused seam cases, all 1,921 interfaces tests and both installed task-shell
cases pass. `a1-headed-native.xml` records the native default/larger pass;
earlier headed receipts retain dependency-cache and sandbox EnumWindows failures
before the native interaction seam. Product/test bytes were unchanged across
those attempts. Independent review approved the atomic A1 delivery; its receipt
is `a1-review.md`. The commit containing this record closes A1.

## Next work

After A1 review and commit, A2 snapshots non-filename column widths at first
visible layout so passive widening goes to Filename only. Preserve existing
Notes-limited resizing and minima; no new sizing policy or persistence. A3
consolidates filters, A4 moves details to a full-height optional right column,
and A5 aligns standalone Inventory/Verify and exposes recorded checksum data.
M1_PLAN owns exact scope, dependencies and gates. Shared source/tests and native
acceptance runs remain serialized; evidence reuse follows dependency identity.

No product changes for A2–A7 have begun. No push, PR or new domain/integrity
feature is authorized. Previous diagnostic catalog repair is committed in
`999a568`; its evidence remains under `build/bridge-catalog-20261004/`.
