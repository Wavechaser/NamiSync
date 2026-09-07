# Production Reduction Register

This is the closed maintenance subregister for the production-ablation pass
under M1-12. It removes redundant implementation and representation
prescriptions; it does not add, defer, or reinterpret an M1 product outcome.
`M1_PLAN.md` remains the sole M1 delivery register. `DEFENSE.md` remains the
authority for supported assumptions, hard walls, and quantitative evidence.

The accepted denominator is PR-0 through PR-9. A new finding does not add a
row. Handle only an active-checkpoint regression or bounded pre-existing defect
per `AGENTS.md`; otherwise record it and request adjudication.

## Main objectives

- Consolidate sync finishing and terminal construction while preserving
  filesystem, verification, recording, and cancellation truth.
- Remove one subsumed history trigger, duplicate event vocabulary and clock
  contracts, and repeated validation of an exact admitted immutable detail.
- Centralize bounded database subject batching and make selection tests protect
  results, snapshot consistency, and bounded work rather than one container.
- Close each reduction with independent expectations, finite controls, consumer
  checks, and adversarial review.

## Scope and decisions

The pass accepts these narrowed outcomes:

1. Require `finish_existing_recording`, consolidate its guarded invocation, and
   remove the absent-dependency reopen fallback. Share verification terminal
   projection without centralizing outcome policy. Do not restructure executor
   settlement or replace its oracle.
2. Remove only `history_events_duplicate_link_update`, which is subsumed by the
   unconditional append-only UPDATE trigger. Retain Python write admission,
   every other SQL trigger, and persistence read validation.
3. Give the seven identical event-detail vocabularies and shared operation-
   reason vocabulary one owner. Reuse an exact base `DetailProjection` after
   admission while retaining mapping/subclass normalization and every real wire
   and persistence-boundary validator.
4. Replace the five identical `Clock.now() -> datetime` declarations with one
   standard-library-only core contract. No other protocol conversion is in
   scope.
5. Make no broader deep-validation reduction. Execution and integrity
   continuation validation remains unchanged.
6. Retain bounded SQL batching. Centralize a production default of 400 subjects
   across the ten variable-`IN` loops; exclude the two `executemany` grouping
   loops. Preserve one-snapshot reads, ordering, complete results, and atomic
   writes. No temp-table, JSON-query, or dynamic-limit replacement is accepted.
7. Keep the current selection implementation. Relax only the six core
   selection-index test families and verifier reporter alias test so they do
   not require `frozenset`, alias identity, private field names, or exact lookup
   counts. Selection results, detached snapshots, refusal, and bounded work
   remain required.

History deliberately advances from schema 6 to 7, contract
`m1-history-v6-event-v5-recording-v1` to
`m1-history-v7-event-v5-recording-v1`, and shared data epoch 6 to 7. Ledger
schema remains 4. Old or mixed database pairs must be rejected through the
existing coordinated-reset contract without mutation or partial pair creation.
The user accepted this pre-release break; it does not authorize migration,
automatic reset, or deletion of database files.

Findings 6 through 10 are rejected. Execution projections, lifecycle claims,
`visible_sequence.py`, desktop infrastructure, and unwired row renderers remain
protected; the last three are valid unintegrated feature components. Also
excluded are generic settlement/lifecycle/serialization engines, oracle
replacement/removal, broad continuation-validation removal, alternate query
engines, and unrelated cleanup.

The frozen baseline is `40fd8a5ca09ee7da60b72352abd8037b7cebb750`
on `codex/production-reduction`. Evidence belongs in the ignored, run-owned
root `build/production-reduction/40fd8a5/`. Its manifest records source and
dirty state, exclusions, interpreter and import origins, Node runtime, exact
commands and collection, skips, raw logs, and hashes. Never overwrite a prior
run. Comparison snapshots are ordinary task evidence; the existing executor
oracle/baseline and SH-G-8 bridge authority remain separate protected
acceptance sources. Do not alter a user-owned `PRODUCTION_ABLATION.md`.

Nondependent checkpoints may run in parallel only with coordinated exact file
ownership, separate atomic commits, and a clean independent reviewer for each.
The dependency column remains binding, and no checkpoint may stage another's
files.

## Regression and assertion dispositions

A regression violates a retained guarantee, including by weakening its only
effective witness. Classify a red test before changing it. Green tests alone do
not establish preservation: each checkpoint also requires independent
expectations, source inspection, fault controls, and harmless-variation
controls. Do not derive expectations from the reduced implementation.

| Bounded population | Retained or relocated | Retired or intentionally changed |
| --- | --- | --- |
| Workflow construction and recording open/enter/finish/exit across fresh/resumed execution, verification, and pause/cancel | Retain finish once, calls/order, accepted prefix, mutation-check precedence, exception retirement, and independent filesystem/recording truth. Relocate guarded finisher mechanics. | Retire absent `finish_existing_recording` support and its reopen/no-op fallback tests. |
| Five verification terminal constructors | Retain exact execution status/phase/bytes and decided verification items/phase, recording, cancellation, and diagnostic. Relocate projection to one pure builder. | Retire duplicated construction only. |
| History schema, pair admission, writer, triggers, and readback | Retain append-only UPDATE rejection, duplicate-link INSERT validity, receipt/hash rules, write classification, and corrupt-read rejection. | Retire only the duplicate-link UPDATE trigger and v6/v6/6 current-contract assertions; old/mixed pairs now reject under v7/v7/7. |
| Event construction, event-v5 serialization/validation, history decode, dispatcher, and browser consumers | Retain exact wire bytes/shape, bounds, omissions, unknown-key/reason refusal, raw alias isolation, normalization, and boundary validation. Relocate vocabulary and exact immutable-detail ownership. | Retire fresh identity/copy of exact base detail, repeated internal traversal, and reflective constructor-bypass/`object.__setattr__` guarantees. |
| Execution, integrity, recorder, history, and inventory clocks | Retain injection, signature, timestamps, and current consumer import names. Relocate five definitions to core. | Retire duplicate definitions only. |
| Seven repository, one history, and two recorder variable-subject SQL loops | Retain complete scoped results, order, relevant-history filtering, one read snapshot, bounded parameters, and atomic writes. Relocate 400 to one policy constant. | Retire repeated literals and exact chunk/query-count prescriptions. |
| `IntegritySelection`, `PostCopySelection`, and verifier progress | Retain membership, exactly-once completion, unknown/duplicate refusal, detached snapshots, progress admission, linear setup, and population-independent per-item membership work. | Retire exact `frozenset`/alias and private-name/metadata/deletion and exact-lookup-sequence assertions. Production stays unchanged. |

The listed intentional differences are not regressions. Changed terminal truth,
weaker real-boundary refusal, lost snapshot consistency, new or replayed
mutation, or population-dependent per-item scanning is a regression.

## Checkpoint register

| ID | Accepted outcome | Depends on | Primary verification | Status |
| --- | --- | --- | --- | --- |
| PR-0 | Freeze contract, qualified baseline, and dispositions. | — | Current-source complete run, provenance manifest, hashes, finite assertion inventory | complete |
| PR-1 | One required existing-run finishing path. | PR-0 | Recording/control cases and call/effect traces | complete |
| PR-2 | One pure verification terminal projection. | PR-1 | Exact terminal-field and phase equivalence | complete |
| PR-3 | Reduced history schema and explicit reset requirement. | PR-0 | Fresh v7 behavior, retained protections, old/mixed refusal | complete |
| PR-4 | One event detail/reason vocabulary. | PR-0 | Independent vocabulary and event-v5 consumer fixtures | complete |
| PR-5 | One core Clock contract. | PR-0 | Five consumers and import contracts | complete |
| PR-6 | Reuse exact admitted immutable detail. | PR-4 | Raw isolation/refusal and wire equivalence | complete |
| PR-7 | One bounded SQL subject-batch policy. | PR-3 | Parameters, results/order, snapshot, atomic writes | complete |
| PR-8 | Representation-independent selection verification. | PR-0 | Selection/progress behavior and structural work bound | complete |
| PR-9 | Integrated reduction closure. | PR-1–PR-8 | Complete/headed suite, oracle repeat 3, controls, adversarial review | pending |

## Detailed checkpoints

### PR-0 — Freeze baseline and evidence

Qualify current-source collection and execution before product/test changes.
Capture exact nodes and parametrizations for every population above; record
baseline failures and skips by node. Hash protected oracle/baseline and SH-G-8
bridge authority without promoting task snapshots to acceptance authority.
The qualified [baseline summary](../build/production-reduction/40fd8a5/baseline-summary.md)
records 4,682 collected tests: the initial run had 4,676 passes, four individually
recorded WinError 1314 capability skips, and two environment-only failures from
a stale ignored project-venv base pointer; the exact two-node rerun passed after
the recorded pointer repair. Import-linter passed all 12 contracts. The
[assertion dispositions](../build/production-reduction/40fd8a5/comparison/assertion-dispositions.md)
and [protected authorities](../build/production-reduction/40fd8a5/protected/authority-inputs.json)
freeze the planned edits and 11 no-change authority paths. Acceptance also
requires clean review of those results, imports from this checkout, no
unexplained failure, and no guarantee without a successor witness. Commit the
register, M1 link, evidence rules, and results as
`docs: define bounded production reduction checkpoints`.

### PR-1 — Consolidate recording finishing

Require the finisher in `SyncDependencies` and affected test doubles. Share
snapshot/invoke/mutation-check/exception-retirement/degradation mechanics;
remove only missing-finisher reopen/no-op branches. Context entry/exit,
finish-once ownership, and settlement decisions stay separate.

Characterize then verify fresh/resumed execute and verify, entry cancellation,
open/finish/close failures, paused cancellation, accepted prefixes, and alias
mutation. Fault controls omit the dependency, skip the required finisher invocation,
invoke it twice, overwrite filesystem truth on recording failure, and move
`RecordingSpec` construction outside its guard. Pass requires baseline
calls/order/arguments and terminal axes, with omission failing at construction;
an effect witness must prove the one required finish occurs exactly once. Run focused workflow tests and
workflows/database/dispatcher departments; update the workflow contract. Clean
review must prove the helper owns mechanics only. Commit as
`refactor(workflows): require and consolidate existing-run finishing`.

Closed after independent source review and evidence recheck: 202 post-execution
tests and the 1,250-test workflows/database/dispatcher union passed. Required
finisher migration also covered five existing consumer cases in `test_workflows.py`
and `test_bridge_resume.py`, preserving their assertions. All four controls
failed the named successor assertions with current-source provenance; the
accepted manifest is `build/production-reduction/pr1/PR1_CONTROL_MANIFEST.json`.
Earlier invalid control attempts remain explicitly non-acceptance evidence.

### PR-2 — Share verification terminal projection

Replace the five constructors with a pure builder receiving already-decided
verification phase/items, recording, cancellation, and diagnostic, and deriving
execution status/phase/bytes from the continuation. It performs no callback,
publication, exclusion, recording, or settlement decision.

Verify success, incomplete verification, cancellation, ordinary failure,
recording-open failure, and prior failed execution followed by verification
trouble. Fault controls overwrite execution status, omit execute phase, drop
cancellation, or lose accepted items. Run workflows and interface result
consumers; update workflow projection ownership. Review rejects configurable
outcome policy. Commit as
`refactor(workflows): share verification terminal projection`.

Closed after clean independent review: eight focused terminal witnesses and
2,181 workflows/interfaces consumer tests passed. Four faults failed the named
status, phase-order, cancellation, and accepted-item assertions. A fresh-verifier
cancellation witness closes the exercised projection gap; all frozen assertions
remain. Accepted receipts and the documentation-only review attestation are in
`build/production-reduction/pr2/run-20260907-161700-final/`, indexed by
`PR2_EVIDENCE_INDEX.md`. Earlier invalid attempts remain non-acceptance.
### PR-3 — Remove the subsumed history trigger

Delete only duplicate-link UPDATE enforcement and apply v7/v7/7. Update current
schema/reset references and fixtures, preserving obsolete and dated evidence.
No migration, legacy decode, automatic reset, or deletion.

Verify fresh, old, mixed, malformed, and altered-topology pairs. Fresh UPDATEs
remain rejected by `history_events_append_only_update`; invalid duplicate
INSERTs remain rejected. Old/mixed pairs refuse without mutation or partial
creation. Preserve receipt/hash, replay/rejection-receipt, and corrupt-readback
checks. Fault controls separately remove the retained UPDATE and INSERT
protections. Run database and workflow consumers. Review the exact generated
schema and current compatibility docs. Commit as
`refactor(database): remove redundant history update trigger`.

Closed after clean independent review: 70 focused tests and 1,099 database/
workflow consumer tests passed. Both retained-trigger controls failed the
specific forbidden-write assertions with candidate imports checked inside each
control process. Reviewed source and evidence remain under
`build/production-reduction/pr3/`; earlier ambiguous controls are unqualified.
The isolated commit was integrated with only the expected CORE documentation merge.

### PR-4 — Consolidate event vocabulary

Own named detail/reason constants in event-v5 and import them into construction;
keep serializers and validators explicit. Tests retain independent literals.
Verify all seven canonical body families, unknown keys/reasons, omission and
boundary behavior through core, dispatcher, database, interfaces, and packaged
JavaScript. A member-add/remove fault must fail an independent consumer fixture.
Review circular imports and widening; update `CORE.md`. Commit as
`refactor(core): share event detail vocabularies`.

Closed after clean independent review: 498 core event tests and 323 dispatcher,
history, interface, and packaged-browser consumer tests passed. Both vocabulary
faults failed through existing public detail-admission tests. Tests and the
event-v5 validator remain unchanged; evidence is in
`build/production-reduction/40fd8a5/pr4/`.

### PR-5 — Centralize Clock

Add one neutral core protocol and import it at execution, integrity, recorder,
history, and inventory while preserving import names, defaults, construction,
and time semantics. Change no other protocol. Verify five signatures, injected
timestamps, consumer departments, and import-linter; a wall-clock or signature
fault must fail. Update the architecture locator. Review that core acquires no
runtime dependency. Commit as `refactor(core): centralize the clock protocol`.

Closed after clean independent review: isolated candidate verification passed
2,530 consumer tests with one capability skip and all 12 import contracts.
The drifting-clock control failed the retained attestation timestamp assertion.
Receipts, raw logs, and matching source hashes are in
`build/production-reduction/pr5/isolated-validation/`.

### PR-6 — Reuse exact immutable detail

Return an exact base `DetailProjection` with zero new omissions and serialize
its validated entries directly. Raw mappings and subclasses still normalize to
an exact base and retain duplicate, Unicode, path, leaf, value, and size checks;
persistence/browser decoders remain independent.

Replace the three frozen fresh-identity/reflective-forgery tests. The user's
2026-09-07 adjudication also permits changing only `admitted is not projection`
to `admitted is projection` in
`test_detail_projection_accepts_only_its_exact_canonical_shape`; retain all of
that test's shape, value, omission, and wire assertions. This one-assertion
correction supplements the frozen inventory; no other family is added. Verify
exact reuse, raw mutable alias isolation, subclass/custom-mapping normalization,
invalid values, omissions, and byte-identical fixtures. Faults retain a mutable
array, bypass duplicates/subclass normalization, or change omissions. Exact
base reuse and one normalized mapping are harmless controls. Run PR-4 consumers
and revise `CORE.md` first to follow DEFENSE rung 3/4. Review proves admitted
immutable variants and retained boundary validation. Commit as
`refactor(core): reuse validated immutable detail projections`.

Closed after clean independent review: 236 focused tests and 2,887 consumer
tests passed, with one capability skip. Four fault controls failed their named
retained normalization/omission witnesses; exact reuse and ordinary mapping
normalization passed. `build/production-reduction/pr6/PR6_ACCEPTANCE_MANIFEST.json`
binds the accepted controls and root-supervised consumer receipt. Interrupted
and child-startup harness attempts remain unqualified; no product fix was made
for them. The user-approved additional identity assertion is recorded above.
### PR-7 — Centralize SQL subject batching

Use `QUERY_SUBJECT_BATCH_SIZE = 400` for exactly the ten variable-`IN` loops.
Preserve SQL, ordering, and transaction boundaries; keep two `executemany`
groups outside scope. Exercise applicable shapes at 0, 1, 399, 400, 401, and
801. Require complete ordered/scoped results, relevant-history filtering, no
partial write, and each statement's source-derived parameter formula; the
largest named shape is at most `2 * batch_size + 1`.

Repeat with a smaller valid batch as the harmless partition control. A snapshot
passes only after witnessing a writer commit between batches while the reader
returns one old snapshot. Faults drop the last chunk, cross location, commit
between writes, or open per-chunk read transactions. Retain index/query-plan
checks; timing is diagnostic. Run database/workflow consumers and update
batch/snapshot mechanism docs. Review all ten formulas and prevent use as a
transaction/retention limit. Commit as
`refactor(database): centralize bounded query batching`.

Closed after clean independent review: 1,147 database/workflow consumer tests
passed. The seven-node smaller-batch control passed; all four faults failed
their retained completeness, scope, atomicity, or snapshot assertions. The
accepted source-bound manifest is
`build/production-reduction/pr7/controls/accepted-control-manifest-002.json`;
`validation/database-workflows-neighborhood-002.receipt.json` records the
terminal consumer run. All ten formulas were checked against source and actual
parameter tuples; both `executemany` groups and transaction bodies remain intact.
### PR-8 — Relax selection representation prescriptions

Change tests only. In the frozen six core families plus verifier alias test,
remove exact type/identity, exact lookup sequence, and private-name/metadata/
deletion assertions; retain semantic parts and unrelated AST guards.

Exercise both selections at 0, 1, 16, 256, and 4,096 deterministic IDs. Verify
selected/pending/completed results, unknown/duplicate refusal, detached
snapshots, pause/resume truth, and progress admission. Source-derived closure
requires linear setup/retained membership and no selected-population enumeration
per completion/progress check. Named counts are drift witnesses, not ceilings.
An alternative immutable set and one detached copy are harmless controls;
faults rescan per item, admit unknown, allow duplicate completion, or alias a
mutable snapshot. Update core/verifier docs. Review rejects both a container
prescription and a results-only quadratic allowance. Run core/verifier/workflow
consumers. Commit as
`test(integrity): decouple selection guarantees from index representation`.

Closed after clean independent review and recheck: 153 focused tests and 1,763
core/verifier/workflow consumer tests passed, with one capability skip. A
non-`frozenset` immutable set plus a detached reporter copy passed; four faults
failed their retained assertions. Accepted source-bound evidence is
`build/production-reduction/pr8/qualified-v2/acceptance-manifest.json`.
Production selection code is unchanged. Earlier evidence is non-acceptance.
### PR-9 — Integrated closure

Cross-check every changed assertion against the frozen inventory. Run complete
ordinary and headed suites, import contracts, active-link and diff checks, and
the unchanged executor oracle three times with identical normalized traces, no
skip/unclassified scenario, snapshot drift, or unresolved finding. Replay all
fault and harmless controls against successor witnesses.

Exercise existing production paths for copy/history readback, resumed failure,
paused cancellation, degraded recording, event consumption, and old-database
refusal. Verify current docs/reset guidance, protected hashes, clean state, and
no edits to findings 6–10. Final clean review assumes each removed mechanism
was the only detector and requires a retained witness or explicit retirement;
it also checks hard walls, failure truth, atomicity, snapshots, bounded work,
and unnecessary abstraction. Update statuses, changelog, handoff, and only a
README milestone synopsis/index that changed. Commit closure as
`docs: close the production reduction verification`.

## Evidence, stop, and resumption

`docs/TESTS.md` and `tests/_departments.py` own test levels and exact department
membership. Each run manifest records focused nodes and department unions. The
established final commands are:

```powershell
& $Py -m pytest -q --dept workflows --dept database --dept dispatcher
& $Py -m pytest -q --dept core --dept verifier --dept workflows
& $Py -m pytest -q -o "addopts="
& $Lint
& $Py -m tools.executor_settlement_audit check --repeat 3
git diff --check
```

PR-0 binds `$Py`, `$Lint`, and Node to verified executables and verifies imports
from this checkout. An unavailable runtime, headed gate, or protected authority
leaves the checkpoint open. PR-7/PR-8 complexity claims are analytical/source-
derived under DEFENSE section 7; named counts are structural witnesses only,
and elapsed time and line count are diagnostics.

Stop for a retained guarantee without an independent successor witness, an
unexplained retained-guarantee failure, scope growth beyond a named population,
or changed protected authority. Apply all AGENTS hard-wall, causal-mechanism,
and WIP recovery rules. In particular, supported-path data loss/corruption,
out-of-root mutation, false terminal/durable success, duplicate mutation, or
inability to preserve work stops the affected checkpoint immediately.

For parallel execution, halt the blocked task and keep independent, nonblocked
tasks moving to their reviewed commits. After those tasks finish, preserve only
the isolated blocked task on its AGENTS recovery branch. A shared blocker also
blocks any task whose guarantees or prerequisites it prevents; it does not
stop unrelated work. This is the user-directed recovery order for this pass.

Current state: PR-0 through PR-8 are complete after clean independent review. PR-9 integrated verification is in progress; the final source checkpoint is PR-7. Preserve user changes, `PRODUCTION_ABLATION.md`,
oracle and baseline, SH-G-8 authority, unintegrated presentation components,
execution projections, and lifecycle claims. Deferred findings are oracle
simplification, broad continuation-validation reduction, further protocol
conversion, alternate query engines, `executemany` grouping, and test cleanup
outside the frozen populations.