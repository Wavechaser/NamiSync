# Latest session handoff

## Plan search and filter controls (2026-09-17)

Plan search stays enabled during an in-flight view refresh. The task shell
retains only the newest later query and dispatches it after the current view
receipt, preserving typing/focus and server-owned view ordering. Switching
away from a retained review does not discard a queued query. Filter controls
now use compact button geometry, translucent neutral rest states, opaque
theme/category active fills and an accent All reset. All, Copy, Move, Update
and Trash always show; remaining categories show only when their complete-plan
counts are positive. Inactive Trash text becomes red above one item.

`PlanReviewState` computes a complete-plan direct-row `filter_counts` facet;
the exact browser summary validator accepts and checks it. No selection,
execution, bridge command, or domain operation scope changed. PRESENTATION,
DESKTOP_UI, FEATURES, README, CHANGELOG and M1_PLAN record the contract.

Focused Plan/frontend/token tests passed (85). The web department passed 1,265
tests, with one skip and 30 headed deselections; the ordinary suite passed
5,172 tests, with five skips and 30 headed deselections. The installed task-shell Plan
witness passed and its confirmation screenshot in `build/evidence` shows the
new counted controls. An initial installed failure revealed the omitted exact
summary validator field; that was corrected before the passing run. A separate
Setup headed witness reaches an empty completed Plan and waits for an
operation row omitted by the earlier rootless-table delivery; it failed twice
at that stale predicate and was not modified in this UI unit.
