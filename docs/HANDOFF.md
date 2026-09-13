# Latest session handoff

## Scrollbar layout and Setup polish (2026-09-13)

Baseline cc5d853 on milestone1. User authorized implementation, independent
review and commits for GUI-R2/S9/S10 and the GUI-D6 M2 dispositions recorded in
M1_PLAN. The execute-task skill governs builder/reviewer separation; root owns
the sole pytest/Node/native gate slot.

GUI-D6 committed as 10d431e: native Fluent overlay integration, verify-only
batching and persistent customizable pair presets are deferred to M2. Preset
records and bridge commands do not exist yet; no runtime behavior was added.

GUI-R2 is complete and independently approved. The development launcher reused
the installed-host smoke helper, whose unconditional display override exposed
Ready in development. The override now requires --expose-ready-status; only
actual smoke readiness witnesses opt in. tools/gui.ps1 stays on the normal
hidden-Ready path. No production readiness, shutdown or process ownership changed.
Evidence in build/gui-icons/: gui-r2-focused-01.txt (55 passed),
gui-r2-headed-01.txt (11 passed), gui-r2-interfaces-01.txt (1,528 passed).

GUI-S9 implementation is active. Shared CSS owns header/body gutter and column
alignment for Setup and gallery file lists. Native Setup tables remain single
tables. One outer horizontal area moves both header and body; the body alone
owns vertical scrolling. Hidden-overflow headers reserve the same stable gutter
without displaying a scrollbar. Retain existing first-interaction column resize
measurement; add no recurring alignment measurements. Always-visible softened
thin thumbs replace pane-hover reveal logic. M1_PLAN records the finite gates.

GUI-S10 follows final shared layout: tighter form label spacing, larger option
gaps, aligned paired path values and authored #2a2a2a dark disabled fill.

No Mica/shadow, native backend, dependencies, batching admission or persistence
changes are authorized in this pass. User-owned development windows remain open;
manual relaunch loads new source. No task-created branch/worktree needs cleanup.
Use unique external basetemps and PIP_NO_CACHE_DIR=1; evidence stays under ignored
build/gui-icons/. Do not close user-owned windows.
