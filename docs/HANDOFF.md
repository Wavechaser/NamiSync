# Latest session handoff

## Scrollbars and batch feedback (2026-09-12)

Baseline 1bbbeb4 on milestone1. User authorized implementation, review and
commits for GUI-S4/S5; broader batch housing remains investigation-only (GUI-D5).

S4 found a supported WebView2 FluentOverlay environment option in the bundled
SDK, but pinned pywebview has no environment-options initialization hook.
Browser flags are documented as development-only. No host, dependency, vendor,
environment or scrollbar CSS change was made. DESKTOP_UI records the supported
native route and CSS alternative; independent review closes this docs-only row.

S5 is being implemented: 60px recent rows, matching folder-column insets,
consistent disabled-cell hover, path-labelled batch rows scoped to their
originating task, and local removal before submission. The global 48-row bound,
single serial runner and exact uncertain retries remain. The originating task
must retain unresolved batch reconciliation rather than hide it on close.
Tests and final product review are still pending; prior GUI-S3 green results
are not this delivery's verification. Root owns one pytest/Node slot.

Relaunch the development app after edits; do not close user-owned windows.
The WCG shadow finding remains diagnostic and unfixed in BUGS.md. Mica, bridge
security, domain behavior and release gates are unchanged.
