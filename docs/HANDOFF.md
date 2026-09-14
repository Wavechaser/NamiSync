# Latest session handoff

## Translucent controls and queued options (2026-09-14)

Baseline f711386 on milestone1. GUI-S14 and GUI-S15 in M1_PLAN are the closed
register for this delivery. User authorized implementation, review and commits.
Execute-task builders own disjoint control-style and batch-state sources;
root owns shared documentation, serialized testing and commits.

S14 replaces RGB control-fill approximations with WinUI alpha roles while
retaining 1.2px strokes, border tuning, accent states, forced colors and separate
popup/Mica materials. S15 captures options at Add pair and removes the later
batch-wide current-form overwrite, preserving admission/retry/removal guards.
Both implementations have passed independent review. Focused evidence in
build/gui-icons/gui-s14-focused05.txt records 31 passing token/installed-gallery
checks; gui-s15-probes.txt records both passing Setup/coordinator regressions.
The combined complete suite passed: gui-s14-s15-complete.txt records 5,013 passed
and 4 existing skips, including all 30 installed checks. S14 is ready to commit;
S15's code is verified and its matching documentation closes next. Earlier S14 receipts exposed stale
opaque-background assumptions in gallery contrast helpers and ambiguous
disabled-rule selectors; final checks retain their thresholds and measure
composited fills against the existing observed backdrop.

No backend/protocol, persistence, native display settings or user-owned window
changes. Existing shadow and M2 dispositions remain deferred. No task-created
branch/worktree. Relaunch the development shell to load changed assets.
