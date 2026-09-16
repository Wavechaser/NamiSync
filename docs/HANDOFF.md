# Latest session handoff

## Plan review GUI refinement (2026-09-17)

GUI-P1–P3 in [M1_PLAN.md](M1_PLAN.md) are complete. The Plan surface now has
separate frozen-settings and status cards plus one table card for search,
operation filter pills, the resizable seven-column table and execution controls.
The gallery and production Plan table both place Modified after Checksum; the
checksum column is blank for Plan facts without a checksum, and dependencies
appear in Notes. Separate header/body scrolling uses the Setup table's stable
gutter and thin-to-wide scrollbar. Name, Size and Modified sort headers cycle
ascending, descending, then canonical path order, with existing chevron icons.
Status and row byte labels use the exact BigInt-backed binary formatter.

The focused interface neighborhood passed 86 tests with five headed tests
deselected. The installed task-shell Plan interaction witness passed, including
the revised filter, sort, resizer and table geometry checks. The installed
gallery light/dark/forced-color witness passed. The standalone byte formatter
boundary probe and `git diff --check` passed. One earlier headed task-shell run
had a dialog focus-containment failure; the immediate repeat with the same
product change passed, so no production focus change was made.

Commits for this task are `f2fc1aa` (register), `27f1a6b`
(formatter) and `4053a53` (integrated surface). The M1-7 quantitative
receipts remain historical to their original source/instrument bytes; this GUI
pass does not recertify current-source scale performance. The separate R7
test/evidence machinery proposal remains in [M1_7_ABLATION_STUDY.md](M1_7_ABLATION_STUDY.md)
and was not changed here.
