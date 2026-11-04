# Latest session — behavioral sweep completed, 2026-11-04

The request-bound fix is committed as `fbd969f0`: CLI and GUI share strict
whole-argv admission before interface/path values. Exact/first-excess and
native argv regressions pass; interfaces qualification accounts for 2,196
distinct passes. Original failures remain in `fix-a1-*` evidence.

The resumed two-phase investigation is complete: 84 cells = 67 bounded clears,
16 reasoned N/A and one open finding. All 311 original BUGS entries have an
owner/mechanism disposition. Fresh probes cover root freshness, native
copy/update/rename/no-op and trash recovery, cancellation, verifier recording,
stale inventory, sparse replay, small queue capacities and adapter/JS races.
Independent review checked receipts and corrected category ownership accounting.

A-2 is OPEN in BUGS: redirected Windows cp1252 history output cannot render a
Japanese filename and returns exit 4/partial report. The identical Python
`-X utf8` read succeeds; underlying files and recorded success remain intact.
No A-2 implementation or installed-app acceptance occurred. The next decision
is disposition of A-2 and transition into the user's later installed-app round.
No third substantive defect emerged. One optional test-fixture consolidation
was identified; no further production refactor is proposed.

Start with `build/bughunt-20261104/evidence/summary-resumed.md`, lane reports,
`corpus-closure.json` and `final-manifest.json`. Earlier stopped reports and
manifests are historical, not current pending status. Recovery `208ad744` was
never merged/cherry-picked; useful content was rebuilt into reviewed records.

Keep `build/bughunt-20261104/fixtures/` plus registered external TEMP roots
`namisync-bughunt-a1-xre87_hl` and `namisync-bughunt-tools-lrgnm16v` until the
later app round ends, then clean exact contained fixture paths while retaining
evidence. Do not remove unrelated ignored caches. Product/tests/tools have no
changes after `fbd969f0`; concurrent release docs remain owned by that session.
M1_PLAN retains release/checkpoint authority; this sweep does not close its
unrelated release gates.
