# Latest session handoff

## GUI-S17 textbox boundaries (2026-09-14)

GUI-S17 clips each textbox fill once, uses the authored 1.2px perimeter, and
makes the neutral/accent 2px strip the actual bottom border. Disabled inputs
flatten every edge; focused inputs retain the shared dual focus ring. Seventy-two
focused checks, the clean installed light/dark/forced gallery, and installed
Setup passed. Adversarial headed review caught and corrected a pressed-state
cascade that initially erased the bottom strip.

## GUI-S16 button boundaries (2026-09-14)

GUI-S16 aligns ordinary and accent button borders with the pinned Microsoft
WinUI resources while retaining the authored 1.2px stroke. Neutral fills clip
to the padding box; accent fills retain border-box sizing. Focused token and
component checks passed all 57 cases; the installed light/dark/forced gallery
gate passed. Textbox behavior remains deferred to GUI-S17.

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
and 4 existing skips, including all 30 installed checks. S14 is committed as
2f4fb8e; S15's code and matching documentation are complete for its separate
commit. README's current GUI synopsis remains accurate; DESKTOP_UI records the
changed queue contract and BUGS records its bounded consequence. Earlier S14 receipts exposed stale
opaque-background assumptions in gallery contrast helpers and ambiguous
disabled-rule selectors; final checks retain their thresholds and measure
composited fills against the existing observed backdrop.

No backend/protocol, persistence, native display settings or user-owned window
changes. Existing shadow and M2 dispositions remain deferred. No task-created
branch/worktree. Relaunch the development shell to load changed assets.

GUI-S18 replaces only the selected checkbox U+2713 pseudo-element with the
pinned local Fluent `checkmark_16_regular.svg` mask. The mixed-state minus and
unrelated lifecycle/status U+2713 cue are unchanged. Focused static verification
passed all 12 design-token checks; the pinned-archive icon check and installed
light/dark/forced gallery check passed.

GUI-S19 keeps the bounded `pageBatch` coordinator intact while projecting batch
rows, count, pending state and messages only into editable Sync Setup forms.
Inventory hides retained sync rows and can start with queued rows; an active
batch still serializes starts, and close/exact-retry ownership guards remain.
The setup-app probe additionally proves an uncertain child cannot start a
separate inventory. All 45 frontend-static checks and the installed headed Setup
flow passed.
