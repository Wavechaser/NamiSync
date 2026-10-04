# Latest session — GUI alignment

2026-10-05 on `milestone1`, base `999a568`. The user ratified the seven-point
GUI alignment register in [M1_PLAN](M1_PLAN.md). A1–A5 are active, in order;
execution-to-Verify navigation (A6) is deferred to M1-10, and all previous-
location/rename redesign (A7) is deferred to a focused session. Standalone
Verify stays on Integrity with Sync disabled. No A7 presentation-boundary
exception was approved.

## Current checkpoint

A1, committed as `4f314b2`, corrects move-reveal recovery in `assets/app.js`. A still-current rejected
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
those attempts. Independent review approved the atomic A1 delivery in
`a1-review.md`.

A2, committed as `498eb24`, snapshots non-filename Plan column widths on the first visible loaded
layout. It reuses the existing width and resize mechanism without CSS/token
changes. The direct probe covers delayed layout and retained widths; installed
task-shell geometry observes passive widening before any resize gesture,
restoration, overflow and existing manual resize behavior. Thirty-six focused
tests, all 1,921 interfaces tests and all six installed task-shell/gallery checks
pass. `a2-native.xml` records the native pass; copied raw receipts retain
`plan_review.initial.passiveSizing` and wheel/installation identity. All frozen
product/test hashes match after acceptance. Independent review approved in
`a2-review.md`.

A3 delivers the shared counted checkbox Filter menu and pinned Regular Filter
icon for Plan and Inventory. The frozen candidate passes 84 focused and 2,286
interfaces/tools checks (three documented tool skips), pinned icon provenance
and all seven installed task-shell/gallery/Inventory cases. Source review
approved; the final review record is `a3-review.md`. The atomic A3 commit contains
this handoff. Raw/frozen evidence uses `a3-*-final*` under the session evidence
root. Pending Escape focus and minimum-window clipping were corrected before
delivery; the menu now uses the known work-panel bounds and dismisses on resize
or outside scrolling, preserving internal scrolling. Replaced filter code/CSS
was removed. Retain the earlier fixture/setup/foreground failures and initial
clipping observation alongside the passing final receipts; none replaces them.

## Next work

After A3 integration, A4 moves details to a full-height optional right column,
and A5 aligns standalone Inventory/Verify and exposes recorded checksum data.
M1_PLAN owns exact scope, dependencies and gates. Shared source/tests and native
acceptance runs remain serialized; evidence reuse follows dependency identity.

No product changes for A4–A7 have begun. No push, PR or new domain/integrity
feature is authorized. Previous diagnostic catalog repair is committed in
`999a568`; its evidence remains under `build/bridge-catalog-20261004/`.
