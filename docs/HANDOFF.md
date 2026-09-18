# Latest session handoff

## Grouped Plan controls, viewport and task digest (2026-09-18)

Plan filters use ordinary button dimensions with category fills and counters.
Copy/Mkdir, Move/Recase, Update/Move update, Trash/Delete (Remove), and
Error/Unsupported/Blocked use split toggles. Main clicks toggle complete groups;
arrows expose counted detail choices, including the whole group. All/Noop/Notice
remain regular toggles. Unsupported is a separate backend facet; immutable plans
have no execution-error rows, so Error's own count is zero.

Search is narrower with an inset submit icon. Enter/icon submits immediately,
sharing a 150 ms repeat guard; ordinary input keeps its trailing debounce and
queued-query behavior. Strict-empty and filtered-empty views have distinct text.

The Plan card puts the switcher, two path rows and two semantic-setting rows
side by side. Settings survive loading. Natural-height Plan/Status cards leave
remaining work-panel height to the table, whose body owns scrolling. Action uses
the same 6rem default/resize minimum. Footer actions align right without a divider,
and the switcher outer radius is concentric.

Built, unexecuted plans use gray **Plan ready**, independently of execution
eligibility. Task tabs share the status digest, showing state, short item/byte
detail, paths or `-`, and aggregate progress; close stays upper right. Loading/
retry and pending-close feedback is retained. Task N remains internal identity.
Selection, safety rules and execution admission are unchanged.

Verification: final focused frontend/token/helper checks passed (63); Python
Plan/category checks passed. Interfaces department: 1,692 passed, one skipped,
one external-fixture root-admission failure. That exact test passed natively
with an external fixture and in the repository sandbox fixture; no domain fix
was made. Installed task-shell checks passed at default and larger native sizes
(2), covering both populated and empty plans, settings/footer visibility,
no page overflow, and confirmation/pause/resume/cancel. Screenshot inspection
and adversarial review completed. The full repository suite was not run.

Evidence: session visualization root
`C:/Users/Spectrum/.codex/visualizations/2026/09/18/01a0b2ed-22b3-7083-a3e1-21f00596391d/`
contains `pytest-gui-j-headed-final`, `pytest-gui-j-interfaces-final2`, and
`pytest-gui-j-drain-native`. Final focused evidence is
`build/pytest-gui-j-final-focused`; screenshot is
`build/evidence/execution-confirmation.png`. M1-8 execution-result presentation
and M1-9 inventory review remain outside this change.
