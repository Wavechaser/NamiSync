# Latest session handoff

## Static Plan folder totals (2026-09-19)

GUI-M2 completes the folder-total work on top of status-card commit 70a9270.
Totals use each distinct canonical destination file path's displayed retained
fact once, including hidden/deselected children and target-file removal sizes.
Moves contribute only at their destination, not prior annotations. One reverse
parent pass reuses child totals without nested double counting; selection
overlays do not rebuild these immutable size facts.

Unknown, conflicting or blocked facts and incomplete scans carry partial notes.
Known blocked bytes still contribute. At the user's direction, totals above
MAX_SIGNED_64 publish null plus an explicit overflow note, including ancestors;
unaffected siblings remain exact. File and execution scalar domains and the
bridge contract are unchanged. Empty directories display zero. Internal
directory identity handles cleanup DELETE as well as MKDIR without changing
the existing container/disclosure flag. Size sorts keep files before folders
and unavailable values last inside each group; other sorts are unchanged.

Verification: 64 focused projection/adapter tests passed, including maximum,
first excess, nested overflow, unaffected siblings, duplicate paths, unknown
members, and real 300-row filter/collapse/selection/window invariance. Browser
probes verify null/notes, blank size rendering, exact maximum and rejection of
above-domain wire sizes. Installed Plan checks passed at default/larger sizes
after the final production corrections. Independent review identified two
introduced edge cases (directory disclosure flag and non-monotonic unknown
member tracking); both are corrected and regression-tested.
Final workflows/interfaces: 2,517 passed, one skipped. Complete scale fixture
gate: 58 passed, one skipped. Final read-only review of fixture/validator changes
found no requirement drift or historical weakening. Diff checks passed.

Current compact scale-fixture expectations and their independent validator were
updated together; legacy schema validation and historical measurement receipts
are untouched. The independent prefix-sum oracle covers every folder in the
100,000-operation/120,000-row fixture and selection invariance. Its elapsed time
includes fixture construction and is diagnostic, not a new performance promise.
The first neighborhood run had a concurrent wheel-build error and stale
fixture-validator failures; sequential packaging passed, and final gate reruns
supersede that run. No full repository suite was needed for this neighborhood.

Recovery af02913 on recovery/gui-m2-folder-totals-20260919 was inspected and
rebuilt, not merged/cherry-picked. Its useful production/tests were integrated
with the approved overflow policy and corrected directory/grouping behavior;
its unfinished HANDOFF and old assumptions are superseded by this document.
The recovery ref and temporary stash 93414b7 remain historical, not merge units.

Evidence root:
C:/Users/Spectrum/.codex/visualizations/2026/09/18/01a0b2ed-22b3-7083-a3e1-21f00596391d/.
Final native evidence: gui-m2-headed-final; sequential packaging: gui-m2-wheel;
final ordinary neighborhood: gui-m2-neighborhood-final. Focused projection/
adapter evidence is build/pytest-gui-m2-reviewed; complete fixture checks are
build/pytest-gui-m2-scale-final2.
