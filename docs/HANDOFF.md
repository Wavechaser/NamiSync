# Latest session — NamiSync app icon, 2026-11-03

The user chose the app icon through three rounds of reviewed candidates. The
final design is a two-sheet copy glyph: an outlined source sheet behind, and a
front sheet of layered paper waves (sky, teal wave, deep front swell). The
color, two-tone and mono SVG masters are in `namisync/interfaces/branding/`.
The flat renders omit the teal wave and close the front sheet with a left-edge
bar, as the user requested. [DESKTOP_UI](DESKTOP_UI.md#app-icon) owns the
description; AGENTS records the folder.

The masters ship as `namisync.interfaces` package data; the wheel-identity gate
requires every tracked file under `namisync/` to ship, so `pyproject.toml` and
its pinned package-data test were updated. Nothing loads them yet. Window,
taskbar and installer icon wiring, `.ico` derivation and hand-tuned 16/24 px
variants are not started and have no M1_PLAN row. The candidate pages and
generator were scratch work outside the repository; the committed SVGs are the
source of truth.

Verification: the exported SVGs were rendered in headless Edge at 192/48/16 px
on light and dark backgrounds. The wheel asset, design-token and package tests
pass. No runtime code changed.

## Carried-over context

M1-12 lifecycle verification closed on 2026-10-30: all 35 installed headed
obligations pass and [M1_PLAN](M1_PLAN.md) records V1–V4 closure. Its evidence
is in `build/m1-12-20261030/`. Recovery `7b0744d4` on
`codex/m1-12-verification-recovery-20261030` holds superseded pause docs only
and is never a merge or cherry-pick unit. Release and DOC-2 remain inactive.

Build artifact cleanup receipts and restore rules are in
`build/build_cleanup_reduction_summary.json` and
`build/build_cleanup_round2_summary.json`. Restore only absent paths and verify
hashes. The pruned recovery branches are retained in
`build/m1-closeout-study-20261029/results/recovery-branches-20261030.bundle`,
with accounting in the adjacent `branch-cleanup-20261030.json`.
