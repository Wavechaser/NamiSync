# Latest session handoff

## Settings shell and GUI refinement (2026-09-12)

GUI-S3 continues from 76028db on milestone1. User authorized implementation,
review and commit. Settings is a local work-area page with the existing theme
selector and a minimal About version line. It preserves tasks, drafts and live
updates; global semantic settings and legal/about link content remain future work.
Task items scroll independently above the Settings button; work content scrolls
separately with stable scrollbar space.

Setup uses Verify execution then Additive sync (on additive/off trash), with
spaced advanced options. Compact inset Clear/caret controls, square Browse and
Refresh, larger New task glyph and right-aligned pair actions follow selective
icon usage. Clear suppresses its own blur admission and invalidates only local
state; an earlier in-flight admission reply cannot restore it. Recent pairs use
gallery typography/corners/surfaces, 64px two-line rows, independent endpoint
statuses and whole-row hover/press/focus. Disabled pairs remain visible/inert.

Arrow Clockwise was added through tools/icons.json and the offline maintenance
tool using the existing pinned archive; no package upgrade or runtime loading.
PLANNER documents exact exclude-filter syntax and effects; FEATURES no longer
claims unsupported glob syntax validation. Completed GUI sections in M1_PLAN
are condensed; unresolved shadow findings and deferred product outcomes remain.

Independent adversarial review approved the product, fixtures and documentation.
Verification passed: ordinary suite 4,979 passed, four existing skips; all 30
headed interface tests passed. After the gallery layout correction, all four
headed gallery tests and its ordinary contract checks passed again. Icon archive
check and all 12 import contracts passed. Ignored build/gui-icons/gui-s3-* logs
retain evidence (ordinary-01, headed-all-03, gallery-final-01 and
gallery-ordinary-final). One pytest/Node slot, fresh external basetemps,
PIP_NO_CACHE_DIR=1. Real CDP pointer checks forward native
dispatch unchanged, prove Clear sends zero admission requests, and verify
whole-row hover/press over status cells. Existing lifecycle/frozen/batch/retry
witnesses remain; no backend source or protocol change.

The gallery keeps natural page height rather than the task shell's fixed-height
layout; its installed guard rejects overlapping top-level sections. Theme/rail
fixtures now enter Settings and distinguish task specimens from navigation.
The shell tree fixture replaces Settings before checking 200% reflow, matching
exclusive production work pages; no post-zoom focus adjustment masks clipping.
No tests were retired and no worktree or recovery branch was created.

The development launcher does not hot reload: relaunch after delivery.
Do not close user-owned windows. Transparent WebView screenshots support
geometry inspection; their alpha handling is not evidence about native Mica
colors or compositor health.

The earlier WCG shadow investigation remains diagnostic and unfixed:
10-bpc WCG SDR dark key shadows over translucent cards can halo. Mica remains
required; BUGS owns the findings and limitations. No display setting, shadow
workaround or release gate was changed here.
