# Latest session handoff

## Completion

ST-H and ST-0 through ST-6 are complete on `milestone1-anthony` under
[TEST_REFINEMENT.md](TEST_REFINEMENT.md). The user resumed after the ST-2 pause;
no further checkpoint was started. Independent GPT reviewers approved the
remaining implementation and final evidence. Consult Claude only when the user
explicitly requests it. Ignore the user-owned root PRODUCTION_ABLATION.md while
it exists.

## Delivered this session

- `72779a6`: share integrity-selection setup while preserving rejection
  behavior, replay order, independent lookup windows and the private-reader fence.
- `a174597`: share exact light/dark/automatic-theme extraction at two visual
  test sites; motion assertions and protected visual consumers remain unchanged.
- `07f9276`: remove seven picker predicate spellings and the command-immutability
  spelling assertion, backed by existing ordinary behavioral tests.
- ST-6 closes the combined evidence and incorporates the preserved study edits
  in the final documentation-only commit.

The full refinement diff from `1026541` is a diagnostic net increase of 27 test
and harness lines: ST-H -2, ST-1 +47, ST-2 -16, ST-3 +7, ST-4 -1, ST-5 -8.
This is limited structural refinement, not a bulk-reduction result. Production,
dependencies, the settlement oracle and SH-G-8 authority remain unchanged.
The superseded recovery branch was already pruned after ST-0 review; its WIP
commit was never merged or cherry-picked. Earlier checkpoint details remain in
Git and the owning register rather than a parallel handoff history.

## Final verification

- Combined replay: 68 accepted cases, comprising 63 faults and five harmless
  variations, with direct node/assertion attribution and restored source bytes.
- Qualified complete suite: 4,678 passed, four unchanged WinError 1314 capability
  skips, no failures or errors; 343.89 seconds.
- Source-matched ST-5 evidence: 4,650 ordinary passes/four skips, 28 headed
  interface passes, and all 12 import contracts kept.
- All 123 protected qualified files match frozen raw hashes. All eight protected
  functions and the exact owner inventory retain canonical source/AST identity.
  Two ST-1 raw function segments differ only by recorded newline normalization.

Evidence remains under `build/test-refinement/1026541/`. ST-6 manifest.json and
summary.json own replay; complete-attempt-03.* and actual-collection-origins.json
own the accepted complete run; protected-reconciliation.json and
evidence-reuse.json own identity. archive-manifest-v2.json hashes the retained
24-file source/evidence archive. Rejected attempts remain uncredited.

## Operational context

The live `.venv` is stale. Use Python 3.13.14 from
`build/test-refinement/1026541/baseline/checkout/.venv/Scripts/python.exe` with
that qualified checkout set as the actual tool working directory. Merely writing
that path into a receipt does not change process cwd. Two rejected ST-6 complete
attempts ran live while recording the intended qualified cwd; the accepted run
verified actual collection, product and tool origins before execution. These
invocation errors and the corrected replay-anchor errors are not product defects.

The qualified checkout contains the final tests over the frozen product baseline.
Use the explicit Node executable in its verification receipts. Broad verification
uses pytest's external default temp directory; mutation probes use isolated
per-run caches and restore every changed byte. Do not repeat suites solely to
recover provenance. The original pre-existing study documents remain snapshotted
in st-0-inputs/ and are now deliberately incorporated in the final documentation.
