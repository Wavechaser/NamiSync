# Latest session handoff

## Scoped, rootless Plan selection (2026-09-17)

Plan bulk selection is now an explicit tri-state header checkbox. Header and
folder gestures target selectable operations matching the server's active
search/filter query across all windows and collapsed descendants; navigation
alone never changes selection, and Execute still uses the complete selection.
The bridge sends only compact intent plus expected view/selection revisions.
The task registry resolves membership under its task lock and calls one
workflow selection mutation; receipt identity includes the view revision.
Safety exclusions and dependency closure remain workflow-owned. Filtered
folder checkbox states reflect their scoped membership; Status counts remain
complete-plan facts.

The synthetic Plan root remains internal but is omitted from public table
windows. Public offsets, totals, row indexes/depths, parent/child indexes and
anchors use rootless coordinates; the header is the sole whole-view control.
The root node cannot be selected through a row gesture. BRIDGE, PRESENTATION,
INTERFACES, FEATURES, DESKTOP_UI and the M1 delivery register reflect the new
contract, including the retired filter-independent Plan folder rule. The
historical M1-7 scale receipts remain tied to their original source/instrument;
they do not recertify this change.

The 120,000-operation scoped server witness matched 16,667 Copy operations
and completed membership resolution, workflow mutation and projection refresh
in 1.207 seconds on this host (10-second diagnostic gate). The focused
cross-layer neighborhood passed 531 tests before the final rootless/edge-case
refinement. The final ordinary suite passed 5,171 tests, with five skips and
30 headed deselections; the post-suite operation-bearing-folder assertion
passed separately. The installed headed Plan flow passed on repeat after one
intermittent modal focus-containment failure; no modal code changed. A
pre-existing raw `transparent` literal in the Plan sort CSS failed the first
ordinary-suite token guard (5,168 passed); a separate tested token correction
was committed as `6425fa7`.
