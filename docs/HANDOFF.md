# Latest session — review follow-ups in progress

2026-10-11. User approved M1_PLAN Review follow-ups based on `350af26`:
RF1 scroll-read regression, RF2 badge/annotation/chevrons, RF3 no-op/skip display;
RI1 initial loading and RI2 axis-lock remain investigation-only. Further scroll
optimization is closed. Work is on milestone1; no unrelated changes or worktrees.

RF1 is verified for its atomic fix commit. Plan input capture now retires only
highlight intent; explicit navigation/view/lifecycle still retire scroll demand.
Inventory/tree input cancellation targets keyboard requests, preserving compatible
scroll reads. Exact external-generation policy and one-read/256-row bounds stay.
Source changed only app.js/tree.js, with existing Plan/Inventory/tree probes and
PRESENTATION updated. Independent review found no source blocker.

Evidence: build/review-followups-20261011/. Valid red rf1-red-event-03 reproduces
Plan replacement reads 3 vs 2 and Inventory 10 vs 3 through repeated input events.
Green rf1-green-event-03 passes 4 probes including keyboard interruption and
admitted mutation custody. rf1-neighborhood-01 passes 2,385 interfaces/tools tests,
3 existing symlink-privilege skips, 195.48s. Installed tree passes rf1-native-01;
Inventory/shell pass unchanged rf1-native-retry-01 (2 in 44.49s) with user foreground
coordination. Retain failed native-01: Inventory's All filter target lacked size/
hit ownership despite foreground ownership; shell stopped before context input.
No RF1 path to the three-row filter fixture was found; retry required no code fix.

RF2 read-only design: compensate the move badge's 9px internal inset to align text;
90%/80% fill opacity only, 4px annotation separation, stronger Inventory disclosure
reset to prevent inherited outer rotation plus child rotation. Reuse existing
Microsoft-derived roles and chevrons; preserve focus/forced colors. Existing
gallery receipts/validators/samples and token provenance are direct consumers.
No RF2 implementation yet. RF3 follows using result skipped+reason noop versus
user-deselected, without executor changes.

RI1 trace: routing waits for review/loading state, empty renderers hide tables.
Propose immediate existing review shell with Checking folders then Planning/
Scanning and blank table; preserve refusal and uncertain outcome recovery.
Cold scan/admission/full projection/initial indexes were excluded from C5 timing;
profile those stages before choosing optimization. RI2: mouse wheel/tilt over
rows, nested axis scrollers and Chromium wheel target retention are plausible,
not reproduced in installed runtime. Propose trusted-delta/scroll-position
observation and same-host nested versus single-scroller comparison. No larger
implementation authorized. M1_PLAN records the bounded source findings.

No native/test process remains active. Default sandbox launch fails; justified
host pwsh works. Freeze all tracked writers during verify.ps1 manifest gates.
Exact integration hashes and cleanup belong in the evidence integration record.
