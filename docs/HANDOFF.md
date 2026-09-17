# Latest session handoff

## Plan review presentation and highlighted rows (2026-09-17)

The Plan review now has compact, category-colored filter buttons with ordinary
button fills at rest; a narrower right-aligned search field; stable Plan and
Status cards during view refresh; an ISO Modified column; and a tiered status.
The status says **Plan ready** when a valid plan has no selected operations,
**Ready to execute** only when preflight passes and selection is nonempty, and
**Plan needs attention** when preflight refuses it. Execute uses the same gate.

Python owns row highlights, anchor, focus and revision. Browser click/keyboard
gestures carry endpoint IDs and revisions, not operation lists. Ranges resolve
against the complete ordered view; window rows carry only their highlight flags.
Search/filter changes clear highlights; sorting, collapse and scrolling do not.
A checkbox inside the highlight applies one server-side selection mutation under
view/highlight/selection revision guards, preserving dependency and safety rules.

The exact command catalogs, presentation/bridge/UI contracts, focused probes,
and the installed Setup/Plan headed witness were updated together. Focused
web/plan-review checks passed (470); the 120k highlighted-selection mutation
cost witness passed in 1.002 seconds. With process-scoped Windows PowerShell
execution policy set to Bypass, the ordinary suite passed: 5,181 passed,
5 skipped, 30 headed deselected. A direct registry highlighted-selection
revision/atomicity check passed after that suite.
The installed headed Setup/Plan witness passed after changing its empty-plan
predicate to require the table card instead of the removed synthetic root row.
Its screenshot capture renders transparent cards against a white fallback in
this host; the same artifact appears in Setup and is not evidence of a new
Plan-only color change.
