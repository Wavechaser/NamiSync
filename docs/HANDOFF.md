# Latest session handoff

## Status composition and folder-total boundary (2026-09-19)

GUI-M1 moves execution controls and icon-only Plan again into the status card's
title row. Concise actionable feedback shares the digest row; both stack and
wrap at narrow card widths. Full feedback remains in a tooltip. The table has
no footer. Size/Modified/Notes share subdued text; dependencies and Risk: none
are omitted without hiding real risk, blockers or notices.

Progress tracks use WinUI's ControlStrongStrokeColorDefault, keeping
translucency local to the background and preserving forced-color Canvas.
The reset glyph comes from the pinned Microsoft catalog, with native 20px
fallback for the small icon slot. Status/rail progress thickness is unchanged.

Verification: icon generation check passed; frontend static suite 49 passed.
Installed gallery passed four modes (Light/Dark/forced/reduced); installed Plan
passed default/larger layouts, warning-row wrapping, control placement, metadata
colors and existing selection/keyboard/confirmation roundtrips. Independent
read-only review found no introduced GUI-M1 regression. Final isolated
interfaces/tools department gate: 2,027 passed, four skipped.

GUI-M2 is NOT delivered. The user defined destination-oriented, distinct-file
static totals, including hidden/deselected children and removal target sizes,
excluding moved prior aliases and nested double counting. Prototype projection,
tests and independent scale manifests are preserved separately while the
numeric-boundary decision is pending. The current bridge only accepts signed-64
row sizes; execution-space admission does not bound all-file totals. Proposed
exact extension affects only Plan row size, bounded by 120,000 × MAX_SIGNED_64.
Alternative: null plus an explicit overflow note. Neither is yet authorized.
Do not merge the prototype or send its larger totals through the current bridge.
Recovery branch: `recovery/gui-m2-folder-totals-20260919`. Its recovery-only
commit is not a merge/cherry-pick unit. Rebuild useful changes into a verified
atomic GUI-M2 commit after the decision; original baseline is `e6ee448`.
M1_PLAN owns scope and resumption; PRESENTATION remains the delivered contract
until a complete reviewed GUI-M2 unit is rebuilt and verified.
Directory classification also needs finishing: retained EntryKind.DIRECTORY
covers both MKDIR and cleanup DELETE. The prototype only handles MKDIR.
Verify empty/removed directory totals and stable folder grouping without changing
selection or disclosure rules; do not add operation-kind special cases.

Evidence root:
C:/Users/Spectrum/.codex/visualizations/2026/09/18/01a0b2ed-22b3-7083-a3e1-21f00596391d/.
Directories: gui-m-headed (four gallery passes, then obsolete risk-label
expectation failure), gui-m-headed-plan (two Plan passes),
gui-m1-isolated (final ordinary gate). Initial mixed-tree ordinary run had
2,029 passes and two stale GUI-M2 scale-manifest failures; independent fixture
corrections passed both focused witnesses. No full repository suite was run.
