# Latest session handoff

## Compact Setup tables and scrollbars (2026-09-13)

Baseline 46da897 on milestone1; S6 committed as 28eafcd. User authorized GUI-S6/S7 implementation,
review and commits. S6 adds conditional batch results with paths, attempted
Verify/deletion settings, short truthful statuses, queued dismissal and
terminal-only Clear results. Results remain with their origin until cleared.
The page-wide 48-row bound, serial runner, fresh admission and exact uncertain
retry remain unchanged; clearing receipts never closes created tasks.

User refinement changed initial 48px rows to 56px and retained single Create
as disabled during batching. Both tables reserve five row slots under 28px
headers (308px total). Add pair precedes Create plan at the right; Create batch
sits below its table at the right. Folder/header insets match. Empty Actions
headers retain accessible names, and first-row column widths prevent overflow.
Routine Setup guidance and the ordinary app Ready label are hidden.

S6 verification passed. Independent source review closed the column
width and missing geometry-assertion findings. Installed receipts exercise
queued/settled batch overflow at full and 32rem widths, inert recent placeholders,
56px/28px/308px geometry, native row hover/press and result clearing. Production
recents remain capped at five; seven actual batch rows exercise overflow.
The finite host-status consumer migration makes materials/shell/native test
fixtures explicitly show their own completion markers; production Ready stays
hidden. One dark gallery measurement failed generically and did not reproduce;
no gallery/product workaround was added.

Final evidence: gui-s6-ordinary-01.txt records 4,979 passed and four existing
skips; gui-s6-headed-final-01.txt records all three Setup/shell/task-rail checks
passed. Gallery/material/native checks passed before the Setup assertion in
gui-s6-headed-all-03.txt; subsequent product edits affected Setup only.
gui-s6-imports-01.txt records all 12 import contracts kept. Direct tooltip and
settings-cell consumers were migrated without retiring assertions.

S7 implements the chosen 10px fixed scrollbar gutter, 2px pane-hover thumb and
6px direct-hover/drag thumb in components.css for the eight existing scroll
owners. It uses neutral theme tokens, rounded ends and equal hover/active paint;
forced colors retain browser defaults. Native overlay painting, fading and
input-mode awareness are not promised. The first interface department run passed all
1,525 checks (gui-s7-interfaces-02.txt); all 30 installed interface scenarios now pass (gui-r1-headed-01.txt).
No host flags, vendor changes or dependency updates were made. Mica and the
unresolved WCG shadow diagnosis remain unchanged.

Evidence logs use ignored build/gui-icons/gui-s6-* and gui-s7-* with unique external
basetemps and PIP_NO_CACHE_DIR=1. Root owns one pytest/Node slot. Do not close
user-owned windows; relaunch the development app to load committed changes.

GUI-R1 corrects native close-status visibility after Ready was hidden and gives
the legacy installed fixture an explicit display override for its literal Ready
witness. No handshake or shutdown policy changed. Independent review approved
the diff with 118 focused and all 30 installed tests passed.

The combined interface rerun passed 1,526 tests (gui-r1-interfaces-01.txt).
GUI-R1 is committed as 65bd02a. GUI-S7 review and native verification are closed;
GUI-S8 is the remaining 8px batch-footer spacing refinement.
