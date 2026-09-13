# Latest session handoff

## Scrollbar layout and Setup polish (2026-09-13)

Baseline cc5d853 on milestone1. User authorized implementation, independent
review and commits for GUI-R2/S9/S10 and the GUI-D6 M2 dispositions recorded in
M1_PLAN. The execute-task skill governs builder/reviewer separation; root owns
the sole pytest/Node/native gate slot.

GUI-D6 committed as 10d431e: native Fluent overlay integration, verify-only
batching and persistent customizable pair presets are deferred to M2. Preset
records and bridge commands do not exist yet; no runtime behavior was added.

GUI-R2 committed as 1398490 and independently approved. The development launcher reused
the installed-host smoke helper, whose unconditional display override exposed
Ready in development. The override now requires --expose-ready-status; only
actual smoke readiness witnesses opt in. tools/gui.ps1 stays on the normal
hidden-Ready path. No production readiness, shutdown or process ownership changed.
Evidence in build/gui-icons/: gui-r2-focused-01.txt (55 passed),
gui-r2-headed-01.txt (11 passed), gui-r2-interfaces-01.txt (1,528 passed).

GUI-S9 committed as 42e86d1 and independently approved. Shared CSS owns stable
header/body gutters and column alignment for Setup and gallery file lists.
One outer horizontal scroll area moves both; the body alone scrolls vertically.
Intrinsic header sizing preserves resized tracks without JS correction loops.
Native table semantics, five 56px slots and forced-color fallback remain.
Softened thin thumbs are always visible and widen on direct hover/drag.
Final root evidence in build/gui-icons/: gui-s9-final-focused.txt (84 passed),
gui-s9-final-ordinary.txt (4,983 passed, four existing Windows symlink-privilege
skips; includes interfaces), gui-s9-final-headed.txt (all 30 passed).
Temporary diagnostic hooks were removed; only ignored evidence artifacts remain.

GUI-S10 is complete and independently approved: tighter form label spacing,
larger option gaps, aligned paired path values and authored #2a2a2a dark disabled
fill. Light, forced-color and transparent controls remain unchanged. Root evidence:
build/gui-icons/gui-s10-focused.txt (78 passed, including installed Setup and
light/dark/forced gallery), gui-s10-interfaces.txt (1,528 passed). The generated
Setup capture confirms aligned paths; CDP captures of Mica are not color-health
evidence. No tests were retired and no temporary diagnostic hooks remain.

All accepted rows are complete. Further M1 slices still require their own user
instruction. README's M2 synopsis is current; no additional overview change was
needed for spacing and scrollbar refinements.

No Mica/shadow, native backend, dependencies, batching admission or persistence
changes are authorized in this pass. User-owned development windows remain open;
manual relaunch loads new source. No task-created branch/worktree needs cleanup.
Use unique external basetemps and PIP_NO_CACHE_DIR=1; evidence stays under ignored
build/gui-icons/. Do not close user-owned windows.
