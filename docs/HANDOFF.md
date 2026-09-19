# Latest session handoff

## Plan terminology and planning feedback (2026-09-19)

GUI-N completes a presentation-only polish unit on baseline 7cf4448.
Plan actions, filters and detail menus use sentence-case friendly names while
canonical bridge/filter keys remain unchanged. DESKTOP_UI owns the explicit
shown/hidden Notes table: hide five redundant low-risk operation reasons only
without risk, blockers or selection exclusions. Keep consequential details,
free-form/unknown notes (including inherited-property-shaped names), and moved
files' prior-location hierarchy. No scan, selection or execution policy changed.

Semantic fields reserve an 8rem settings slot and fixed icon/text columns.
Verify on uses accent arrow-sync-checkmark; Verify off uses gray arrow-sync;
Trash uses gray delete; Additive uses accent document-add. Only icons change
color. Document-add was added through the pinned Microsoft Fluent icon tool;
registry, native SVGs and provenance are generated, not hand-edited.

The shared task digest shows indeterminate planning during a dispatched start,
active planning without a summary, and completed-review loading. The dispatch
transition repaints before awaiting the response. The loading Plan status card
uses the same digest. Ready plans and failures stop animation; Inventory and
execution retain their own states. The existing Plan-again trace helper was
updated at its exact dispatch anchor without weakening restoration checks.

Verification:

- Interfaces/tools: 2,033 passed, four skipped, 3,197 deselected.
- Final frontend: 50 passed, including supported WebView2 API-floor checks,
  notes visibility and the held-response dispatch repaint witness.
- Pinned icon archive check and 34 focused icon tests passed.
- Installed WebView2: six passed, 18 deselected; four gallery modes plus
  default/larger Plan scenarios. Gallery checks toggle all requested semantic
  icons/colors without moving field bounds, and exercise planning/error/ready
  progress. Existing selection/navigation/layout checks remain green.
- Independent read-only adversarial review and final diff checks passed.

The first broad attempt used a repository-local temp root refused by the
custody harness; rerun used the external evidence root. The next attempt found
the stale Plan-again trace anchor; final broad checks pass after its migration.
A final unknown-note guard initially used a newer JS API; the compatible
own-property equivalent passed all 50 frontend checks. That equivalent lookup
was the only production change after the installed wheel had been built; it
does not change layout or state behavior.

Evidence root:
C:/Users/Spectrum/.codex/visualizations/2026/09/18/01a0b2ed-22b3-7083-a3e1-21f00596391d/.
Broad checks: gui-n-departments-final; installed checks: gui-n-headed.
Final frontend: build/pytest-gui-n-frontend-compat.
Restart the development app to reload packaged frontend assets.

Earlier GUI-M2 recovery af02913 on recovery/gui-m2-folder-totals-20260919 and
temporary stash 93414b7 remain historical, not merge units. Their useful changes
were rebuilt and integrated in 7cf4448; no recovery work is pending here.
