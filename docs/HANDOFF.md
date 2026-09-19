# Latest session handoff

## Plan spacing and byte precision (2026-09-20)

GUI-O completes one presentation-only polish unit on baseline c552537.

- Tertiary foreground is #616161 Light and #adadad Dark (including automatic
  dark), with CanvasText in forced colors. Size/Modified/Notes and rail paths
  consume it; status text and primary content keep their existing roles.
- Filter label/count spans use a dedicated gap instead of word-spacing;
  menu counts align right and controls retain accessible combined labels.
- Setup says Sync/Integrity without changing inventory behavior or mode keys.
- Status-card Plan again is square. Progress tracks use button-rest fill,
  preserving active fill and forced-color behavior.
- Task detail/path/progress endpoints move inward 10px to an 18px right inset.
  Plan and task-rail paths use equal-width Source/Target label slots.
- Shared byte formatting uses exact integer bytes below 1 KiB and two fixed
  decimals from KiB upward, including trailing zeroes. BigInt rounding and
  unit promotion remain exact; raw facts and sorting are unchanged.

DESKTOP_UI and PRESENTATION describe the changed visual/precision contracts.
No scan, selection, lifecycle, execution, bridge or filesystem policy changed.

Verification:

- Interfaces/tools: 2,033 passed, four skipped, 3,197 deselected.
- Final frontend/token checks: 62 passed, including decimal rounding/promotion.
- Installed gallery: light/dark/forced/reduced passed. Added rendered checks
  for tertiary metadata/path colors, normal interword spacing, menu count
  alignment, square reset, path starts and 18px task-detail endpoints.
- Installed Plan: default passed; larger passed on fresh rerun.
- Independent review and final diff checks passed.

The first broad run encountered old progress-track expectations; they were
migrated with the changed token contract, then the full gate passed. Initial
gallery failure was a new test selector including Settings (which has no task
paths); it now checks actual task tabs. The combined installed run passed all
gallery checks and default Plan, but larger failed at page_initial_ready.
Its log showed no layout cause; one fresh larger-only rerun passed without a
product change. The failed evidence is retained rather than called a pass.

Evidence root:
C:/Users/Spectrum/.codex/visualizations/2026/09/18/01a0b2ed-22b3-7083-a3e1-21f00596391d/.
Broad gate: gui-o-departments-final. Frontend/token: build/pytest-gui-o-visual-final.
Installed gallery/default: gui-o-headed-final; larger: gui-o-larger-retry.
Restart the development app to reload frontend assets.

Earlier GUI-M2 recovery af02913 on recovery/gui-m2-folder-totals-20260919 and
temporary stash 93414b7 remain historical, not merge units. Their useful changes
were rebuilt and integrated in 7cf4448; no recovery work is pending here.
