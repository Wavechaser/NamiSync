Notes for "Admission and bridge closeout (2026-09-27)": text files chosen from `build/admission-bridge-closeout-20260927/`, verbatim, each under an H1 naming its source path. Non-Markdown files are fenced. JSON is in `data.json`.

# `build/admission-bridge-closeout-20260927/bridge-interfaces-overlap.md`

# Interfaces department overlap receipt

Command: `.\.venv\Scripts\python.exe -m pytest -q --dept interfaces`

This run began while the IR-DB builder was modifying shared product source. It
finished with 1,813 passes, two failures, five errors and 3,593 deselections in
121.20 seconds. The installed-wheel fixture rejected source identity drift in
`namisync/db/contracts.py` and `namisync/workflows/database_pair.py`. Two
`tests/test_service.py` runtime-close nodes failed because their `object.__new__`
doubles had no new `_database_pair_lock` when `LocalWorkflowRuntime.close()`
reached `runtime.py:1289`:

- `test_workflow_runtime_retains_a_store_whose_close_failed`
- `test_concurrent_workflow_runtime_close_waits_for_failed_attempt`

The latter also produced a teardown thread error for the same missing lock.
This is an invalid integrated gate during concurrent edits, not a bridge result.
Root and the IR-DB builder were notified. A clean integrated suite follows
both source freezes.

# `build/admission-bridge-closeout-20260927/bridge-review.md`

# IR-BRIDGE final independent review

2026-09-27, product/base 639b2ea. Read-only reviewer database_design had no
bridge builder history. Final disposition: approved; no remaining findings.

Reviewed driver/page/child, focused tests and executable page probe, BRIDGE,
PERFORMANCE, BUGS, CHANGELOG, M1_PLAN and HANDOFF. Canonical fixture scalar
decoding and item-free terminals retain exact ordered reliable witnesses.
Report failure stops sampling, releases queue reservations, captures original
error/active-report metadata, publishes failure before marker, and settles
cooperative producer cancellation through unchanged production host policy.

Review corrections resolved: capture the failure payload before asynchronous
cleanup clears active_report; preserve raw milestones and unfinished streams
on normal incomplete exit as well as exceptions. The latter has a real-file
regression proving exact bytes survive TemporaryDirectory cleanup.

Final ordinary: bridge-ordinary-final.xml/log, 5,380 passed, 4 privilege-related
skips, 34 headed deselections, 281.57 seconds, exit 0. Focused final:
bridge-focused-retention.xml, 35 passed. CRLF page probe passed; later retention
change did not alter the page/probe. Original DB import and installed Setup
passes remain valid because product bytes are unchanged.

bridge-full-final.json: complete, measurement_valid true, archived
639b2ea8641d87b5cc2df09022bd91cb01c8afe9, four valid sessions with 150 ordered
reliable events and one terminal event/record each, 1,500/150 producer counts,
no gaps/startup/browser errors and monotonic progress. CLI exited 0.
Historical passed/event_passed false and custody incomplete are not new
acceptance. Frozen custody JSON is unchanged.

bridge-injected-report-failure.json: intentional rejection after five accepted
batches, first error report:samples, active report index 6/count 100, no parent
failure and normal host exit. Raw failure complete=false and final complete=true/
exit_code=0 retain identical browser failure and sample manifest. Independently
authenticated 500 samples (SHA256 1e74a06d4d5ec4f3852386b915bf947fdb1daaa57f3531dee9ddc56f39aeece2).
All four unfinished producer timing files remain (7,684–7,712 bytes), without
completed producer manifests. The normal native control returned exit 0.

Earlier observations are retained as bridge-full-before-retention.json,
bridge-control-before-checker.json/log and bridge-control-before-retention.json/log.
The control's punctuation expectation was corrected from actual bridge sources.
The CLI's no-overwrite refusal and unsupported replacement suggestion are in
bridge-report-replacement-guard.log and bridge-report-unsupported-option.log;
that separate pre-existing guidance defect is logged/deferred, with no CLI edit.
Final success used a fresh output name.

bridge-docs-check.json: 120 local links, no errors. Final diff check passed.
No source changes followed these final test/native receipts; final status prose
marks the approved row complete before commit.

# `build/admission-bridge-closeout-20260927/closeout-review.md`

# IR-CLOSE independent review

Reviewer: bridge_design, read-only unrelated outcome review; base a0205c08.
No blocking findings. Independently reran the historical line mapper and read
runtime-failure-site plus execution-confirmation-driver: checkpoint plan_again,
focus false, completed/released session; zero-based490 is the focus-ring wait.
The retained wait has independent sequencing value: filter work is asynchronous
and production disables Plan again while review.pending is non-null. Helper and
product assets are unchanged. BUGS classifications removed without adding an
environment detector; TESTS retains evidence/limits and native input ownership.
Scoped diff check passed (line-ending notices only). No native test needed.
DB/bridge implementation and AB-8 deferral were outside this review.

# `build/admission-bridge-closeout-20260927/db-implementation.md`

# IR-DB implementation and focused evidence

The approved cold/live distinction is implemented by two concrete optional
`DatabaseConnectionOwner` slots on `LocalWorkflowRuntime`, under its existing
pair lock. Each role is cold-preflighted only when its first actual reader or
recorder needs it. Public cold classification and fresh Plan remain noncreating.
Standalone history reading retains independence from ledger existence.

Each owner pins an ordinary read-only SQLite connection; live checks enforce
main-file identity, journal absence and exact schema/marker validation in a
short SQLite read transaction. Opens validate before writable connection
configuration and validate the new connection's own snapshot. There is no
global registry, cached READY state, unbound token, retry loop or SHM exemption
in cold validation. Runtime closes query readers/history writer before role
owners and retains an owner whose close failed for a quiescent close retry.

Finite changed product population: `db/contracts.py`, `db/repositories.py`,
`db/history.py`, `db/recorder.py`, `workflows/database_pair.py`,
`workflows/runtime.py`, `workflows/inventory.py`. Existing schema/connection
factories, SerializedWriter and source snapshot mechanism remain unchanged.
Inventory dependency and literal/remembered binding helpers propagate the same
lazy runtime owner; correspondence, visibility, inventory, integrity, sync
recording and history store all use it. Standalone constructors default to cold
admission. `tests/test_service.py` has two constructor-bypassing close doubles;
their explicit lock/owner state was updated for the actual close population.

Regression: `db-before.xml` retains one failure on the previous product:
committing a benign WAL `user_version` update from inside the schema validator
makes runtime pair admission falsely refuse. Final controls exercise the same
interleaving through `prepare_plan`, with ordinary SQLite reads as well as WAL
commits, independently for both roles. They assert completion of the activity.
The read control advances WAL before admission so source read-mark movement is
ordinary SQLite activity. Tests do not depend on scheduling a probabilistic
race loop.

Focused receipts:

- `db-first.xml`: 204 passes (cold-contract matrix plus initial live regression).
- `db-focused-01.xml`: 383 passes, 21 failures; old runtime-reader instrumentation
  observed constructor-local cold preflight rather than role-owner adoption.
  The existing observations were migrated to actual cold owner adoption;
  query-reopen expectations now require live revalidation, with corruption
  refusal covered explicitly. This failed receipt is retained.
- `db-readers-02.xml`: 42 passes after instrumentation migration.
- `db-readers-03.xml`: 57 passes, adding live damage and Windows lifetime controls.
- `db-focused-04.xml`: 624 passes across runtime readers, cold contracts,
  inventory runtime/workflow, repositories, history and recorder setup/move.
- `db-readers-05.xml`: 62 passes including original reader activity and failed
  role-owner close retry controls.
- `db-readers-service-06.xml`: 64 passes after final fresh-Plan assertion and
  direct service-close test-double migration.

Live negatives cover wrong marker, extra schema table, journal presence and
observed identity mismatch before writer configuration; wrong role/path and
managed-root placement remain refused. Actual Windows rename fails while a
role owner pins the main and succeeds after runtime close. Mixed cold/live pair
checks and failed-reader reopen also have direct coverage.

All product bytes froze before root's installed Setup seam. Root owns the
installed/ordinary/import gates and independent final review. These focused
receipts alone do not claim checkpoint completion.

Root ordinary run retained `db-ordinary.xml`/log with 5,378 passes and one
direct-consumer fixture failure: the correspondence-bounds test wrote `present`
instead of a database and its fake repository accepted only a path. The test
now creates a real ledger and checks the supplied live owner's path/role while
keeping all original current-scan bounds assertions. No product correction was
needed. `db-workflows-fixture-07.xml`: all 52 tests in `test_workflows.py` pass.
Include that fixture file in the final IR-DB review/commit population.

# `build/admission-bridge-closeout-20260927/db-review.md`

# IR-DB final independent review

2026-09-27, base 8f75f75. Read-only reviewer bridge_design had no DB builder
history. Final disposition: approved, no blocking findings.

Reviewed actual db/workflow diff, all identified direct consumers, runtime
reader tests, service-close doubles, correspondence fixture correction, and
DATABASE/DEFENSE/BUGS/CHANGELOG/M1_PLAN/HANDOFF. Cold snapshot admission remains
unchanged. Live owners use current SQL transactions, role/path/identity and
journal checks; placement precedes writers; independent role reads remain
valid; failed shutdown retains ownership for retry. No cached READY or generic
hash bypass. Windows handle pin and reader/WAL activity controls were inspected.

Final ordinary receipt db-ordinary-final.xml/log: 5,379 passed, 4 skipped
(Windows symlink/reparse privilege unavailable), 34 headed deselections;
exit 0, 276.20 seconds. Installed Setup db-installed-setup.xml/log: 1 passed,
34.17 seconds. Root lint-imports command: 84 files, 394 dependencies,
12 contracts kept, 0 broken. db-docs-check.json: 87 links, no errors.
Scoped diff check passed. Earlier failed/in-flight receipts are retained;
db-implementation.md records the deterministic red regression and focused tests.

No product bytes changed after installed Setup. Final ordinary includes the
corrected fixtures and frozen bridge candidate; bridge's native gates remain
its separate commit responsibility.

# `build/admission-bridge-closeout-20260927/defer-review.md`

# IR-DEFER independent review

2026-09-27, base e8d3613. Read-only reviewer: bridge_design; no builder history
for this documentation outcome. Reviewed TESTS, M1_PLAN, HANDOFF and CHANGELOG.

Approved with no blocking findings. The current helper writes feedback
visibility/text then yields a frame; production rendering resets the same state.
Historical verification records failure followed by unchanged passing reruns,
without captured geometry proving that proposed race. The documentation keeps
the mechanism hypothetical and AB-7 larger-shell attribution tentative because
the intermediate script was not preserved. No CSS, helper, assertion or new
acceptance requirement is introduced. Referenced evidence exists; 84 local links
and scoped git diff --check passed. Root updated only review-status prose after
approval.
