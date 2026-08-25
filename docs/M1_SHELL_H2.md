# Stage 6 Slices 5–6 and Early Slice 7 Implementation Plan

> Active execution checklist ratified on 2026-08-24. `docs/M1_BRIDGE.md` owns
> the exact accepted protocol and `docs/M1_SHELL.md` owns the Stage 6 shell
> sequence; this file is the newest checkpoint reslice and owns the detailed
> acceptance, review, and test boundary for checkpoints 0-12.

## Main objectives

- Deliver the complete Setup → Plan → Execute → Inventory/Integrity workflow, including typed paths, remembered locations, bounded file lists, execution controls, full recorded hashes, and modification times.
- Establish exact event-v5 recording truth: item-local recording degradation remains separate from filesystem outcome and task-wide recording issues.
- Replace the one-session bridge model with process-live tasks that retain reviewable results across navigation and support later manual verification.
- Pull forward Slice 7 lifecycle, retention, shutdown, and event/history epoch work while deferring the history page, global settings page, drag-and-drop, and remaining cosmetic state.

## Locked contract map

The exact accepted target is not duplicated in this checklist.
`M1_BRIDGE.md`'s file map and mapped DR-BR records own field shapes, wire
schemas, command rows, authority order, refusal precedence, and bridge gates.
`DEFENSE.md` §1.3 owns the numeric and retained-resource hard walls. The
locked-contract summaries below define scope and dependencies; the checkpoint
section retains detailed acceptance and test categories without redefining the
exact schemas or hard-wall values. A conflict is resolved in the owning mapped
decision record, not by treating this prose as a second authority.

### Recording and evidence scope

- Keep filesystem outcome, item-local recording status, task recording issues,
  and history audit as independent truth axes.
- A committed item receipt is final; later task or audit degradation cannot
  rewrite it or suppress durable evidence.
- Process-local execution continuation may carry transient evidence only until
  terminal settlement. Retained task views and JavaScript use the bounded
  projections accepted in the bridge records.
- Execution review classifies evidence from one ledger-current snapshot.
  Plans expose no hashes, and current inventory/integrity detail labels
  provenance rather than presenting coincidental state as execution evidence.

### Protocol and persistence scope

- Checkpoint 2 changes only the process-local execution continuation.
  Checkpoint 3 is the coordinated core-event, terminal-summary, bridge-
  validator, ledger, history, CLI, and compatibility cutover with three
  independently testable landing stops.
- The exact `TerminalSummary`, refusal fact, recording fields, database epoch,
  scalar codec, checked-arithmetic policy, and reset posture are owned by the
  mapped bridge decisions and `DEFENSE.md` §1.3.
- Protocol targets are accepted but inactive until their implementation
  checkpoint; current-version documentation remains truthful until then.
- Every checkpoint that activates command rows updates BR-G-32's exact ordered
  production-table test and the JavaScript policy mirror in the same commit.
  Checkpoints 4 and 6 also advance BR-G-46's two reopened map revisions; later
  command additions remain ordinary BR-G-32 revisions.

### Setup, paths, and remembered locations

- Setup freezes every semantic option used by a plan; JavaScript never
  normalizes filters or rereads mutable defaults for an admitted task.
- Picker, typed, and remembered inputs share one workflow-owned local-directory
  admission path and create only bounded, purpose-bound process-local slots.
  Every real start freshly re-admits its roots.
- Desktop admission accepts the reviewed local Windows directory domain and
  rejects file leaves, remote/device spellings, reparses, placeholders, and
  unusable volume facts with typed action-guiding results.
- Recents come only from eligible ledger runs, remain distinct from current
  reachability, and are revalidated when activated. Multi-pair creation is
  serial browser orchestration over ordinary single-task starts.

### Task, review, and retention scope

- A process-live task owns at most one current session while retaining
  separately named compact plan, execution, inventory, integrity, and post-copy
  results across navigation.
- Lifecycle, result, selection, view, and browser request authorities remain
  distinct. One task-operation owner serializes effect-owning lifecycle work;
  the exact claim, lease, epoch, publication, release, and close ordering lives
  only in the mapped bridge records.
- Reliable item facts update compact overlays; terminal transport uses the
  accepted bounded summary rather than sending a full result item collection
  to JavaScript. Producer/core and presentation omission witnesses remain
  separate.
- Plan and inventory trees are server-owned, immutable-generation projections
  with bounded search, filters, windows, anchors, and action scope. A complete
  candidate publishes atomically or not at all.
- Task and projection retention obey `DEFENSE.md` §1.3. The bridge records own
  the complete charged graph, reservation mechanics, retry receipts,
  tombstones, publication-fault behavior, and exact capacity results.
- Setup, plan/execution, inventory/integrity, and task-lifecycle command
  families land only in their named checkpoints. Exact command names, request
  shapes, retry classes, deadlines, and activation rows remain in
  `M1_BRIDGE.md`.

## Committable checkpoints

### Checkpoint execution protocol

The ordered checkpoint list is also the recovery protocol for an implementer
who has no session context. Before starting a checkpoint, confirm that the
preceding row in `M1_SHELL.md` is complete, inventory every existing worktree
change, and reread that checkpoint's mapped `M1_BRIDGE.md` decisions and BR-G
gates plus any `DEFENSE.md` wall it cites. Do not absorb, rewrite, or commit
unrelated or already-started work merely to obtain a clean tree.

Except where a checkpoint lists multiple mandatory commits, its `Commit:` line
names the required activation/closure commit; it does not require all
preparatory work to be compressed into one commit. Preparatory commits may add
types, independent validators, fixtures, backend machinery, or browser code
only while the accepted target remains unreachable from every production
dispatcher, command map, persistence reader, and rendered control. The closure
commit makes the checkpoint coherent at once: no production row points at a
partial backend or UI, and every replaced row loses its old alias in that same
commit. A checkpoint may be `in progress` at a documented safe stop, but it is
not `complete` until this closure lands.

Run focused tests while editing. Before an activation/closure commit, run every
affected producer and consumer department and the ordinary suite for a shared
or cross-department contract; run `lint-imports` when dependency boundaries
move and the installed headed witnesses when a user surface activates. A BR-G
gate closes only with the exact production entry point, counterexample, and
collected `test_br_g_<number>_*` nodes required by `M1_BRIDGE.md`; skipped,
xfail, comment-only, dormant, or uncollected evidence does not count. Record
measurement fixtures and validators before observing acceptance evidence, as
required by `DEFENSE.md`.

If a gate or adversarial review exposes a policy defect, land the policy and
persistent regression in a separate commit, invalidate affected evidence, and
rerun the gate from its declared entry state. Do not weaken a gate or silently
retune a constant to preserve green. At closure, update the checkpoint row in
`M1_SHELL.md`, every owning document's active/inactive wording, and any gate
status changed by the checkpoint in the same commit. When work stops before
the next checkpoint closes, replace `HANDOFF.md` with the exact safe stop,
verification already run, dirty-file ownership, and next command; checkpoint
12 remains the one integrated CHANGELOG and final-documentation closure.

### 0. Ratify the reslice and protocols

This checkpoint was intentionally relanded as five ordered documentation
commits so each authority remains independently reviewable:

1. `docs(bridge): accept the stage 6 second-half contracts`
2. `docs(gui): reslice the stage 6 second half`
3. `docs(defense): record the stage 6 scalar and retention walls`
4. `docs: point component docs at the accepted contracts`
5. `docs: record the stage 6 ratification`

This five-commit boundary supersedes the original single checkpoint-0 commit
shape for atomicity and serviceability; it does not change later checkpoint
numbers or implementation dependencies.

- **Objective:** Make active documentation the decision authority before implementation.
- **Acceptance:** Re-slice M1_SHELL/M1_BRIDGE; place the exact accepted command,
  protocol, ownership, and retention target in the mapped `M1_BRIDGE.md`
  decision records; keep the normative scalar and containment walls in
  `DEFENSE.md`; and reduce other active documents to behavior summaries or
  ownership pointers. Rewrite BR-G-36, BR-G-39, BR-G-41, and BR-G-45; add
  BR-G-47 for Setup/location admission and BR-G-48 for recording/evidence
  handoff.
- **Regression watch:** Find every positive v3/v4 compatibility statement, picker-only claim, nullable `start_plan`, one-session task assumption, full-terminal transport promise, UI-state recent, numeric mtime, and immutable operation-attestation proposal.
- **Tests:** Documentation links/anchors, contract-source locators, targeted
  consistency searches, test-manifest validation, and `git diff --check`.
- **Docs/review:** Update the authorities and replace component restatements
  with links. Keep `TESTS.md` free of a parallel checkpoint/case catalog, mark
  target contracts accepted-but-not-active until their checkpoint, and conduct
  independent architecture/security review.

### 1. Pin recording-axis settlement truth

Commit: `test(executor): pin typed recording settlement truth`

- **Objective:** Establish the expected executor behavior before changing producer contracts.
- **Acceptance:** Extend only the oracle's pre-production typed projection and focused tests; do not change the protected scenario/row manifest, normalized trace, baseline JSON, or semantic hash pin. Pin the four-way matrix exactly: `success.all-nine` COPY = filesystem succeeded, recording `ok`, null reason; `record.copy-failure` = filesystem succeeded, recording `degraded`, `record-write-failed`; `failure.copy-prepublish-cleanup-ok` = filesystem failed, recording `ok`, null reason; and `failure.byte-published.copy` = filesystem failed, recording `degraded`, `unrecorded-mutation`. Also pin `recording.pre-destructive-flush-refusal` to item reason `recording-prerequisite-failed`; `recording.final-flush-degradation` to a successful recording-`ok` item plus only task issue `final-flush-failed`; and `recording.sticky-aggregate-degradation` to a degraded first item, `ok` second item, and sticky degraded aggregate.
- **Regression watch:** Do not change filesystem outcomes, retry traces, journal retirement, durable-state interpretation, recorder order, pause/cancel behavior, or existing baseline facts.
- **Tests:** Executor and tools departments; run `.\.venv\Scripts\python.exe -m tools.executor_settlement_audit check --repeat 3` and require all scenarios/rows, identical normalized traces, no skip, and no unresolved finding.
- **Docs/review:** Update EXECUTOR and TOOLS. Review the new oracle projection separately from production changes.

### 2. Attribute executor recording degradation internally

Commit: `refactor(executor): attribute recording degradation by scope`

- **Objective:** Introduce typed internal item/task attribution without redesigning settlement or changing the live core-event v4 wire yet.
- **Acceptance:** `_record()` returns a typed observation; `ExecutionSet` retains sparse degraded operation IDs/reasons and task issues; identityless transient evidence is tied to that operation’s recording failure. Final flush and restoration divergence remain task-scoped. Advance the exact process-local workflow execution payload to v6 in this checkpoint so attribution and permitted transient attestations survive real dispatcher pause/resume; payload v5 is refused after the cutover. On every terminal path dispatcher nulls the opaque continuation payload reference before publishing/storing the terminal record.
- **Regression watch:** Guard `_Settled`, `_SettlementReduction`, `_record`, `_flush_before_destructive`, `_settle`, publication reducers, resumed-directory restoration, and reliable-emission-before-continuation ordering. No global degradation may assign item status.
- **Tests:** Executor plus workflow/dispatcher neighborhood; first-row-fails/second-commits, committed-copy/later-item-fails, prepublication failure, apply-raised-but-state-matches, rowless immediate linked verify, pause/resume, paused→resumed→terminal payload scrubbing on success/failure/cancel and delayed release, and event-sink rejection. Repeat the settlement oracle three times.
- **Docs/review:** Update EXECUTOR, RECORDER, and WORKFLOWS. Adversarially compare filesystem/recorder traces before and after.

### 3. Stage the exact event-v5 cutover

Commits, in order:

1. `refactor(protocol): prepare dormant event v5 consumers`
2. `feat(protocol): publish exact core event v5`
3. `refactor(protocol): remove legacy event compatibility`

- **Objective:** Publish the new truth contract across every producer and consumer and remove legacy machinery.
- **Position and safe stops:** Keep this checkpoint before checkpoint 4.
  Checkpoint 4's retained task/result model already consumes the exact v5
  `TerminalSummary`, recording axes, and database epoch; moving the cut behind
  checkpoint 7 would build checkpoints 4–7 against a disposable v4 task
  contract. The first commit adds strict v5-specific consumers, validators,
  fixtures, and direct test seams, but keeps every production current-version
  constant, dispatcher, allowlist, history/database reader, and browser route
  exact-v4. The v5 path is unreachable except by its explicit tests, so this
  stop changes neither emitted/persisted behavior nor accepted production
  input. The second commit atomically switches every producer and live consumer
  dispatcher and performs the coordinated database epoch/reset cut; its safe
  stop is a fully working exact-v5 runtime with now-unreachable, read-only v3/v4
  branches still present in source. The third deletes those branches and
  positive fixtures, freezes the one exact version, and closes the checkpoint.
  Never make v5 reachable from production before the coordinated switch, land
  a producer switch before its consumers, or delete compatibility before the
  v5 runtime passes.
- **Acceptance:** Implement the mapped recording, reliable-event,
  terminal-summary, review-limit, scalar-codec, file-identity, and persistence
  decisions from `M1_BRIDGE.md` and `DEFENSE.md` §1.3 across core producers,
  JavaScript, dispatcher views, history, CLI, and service. Store full-width
  Windows file indexes as canonical `FileIndex128` text, obtain native identity
  through the core-owned complete `FILE_ID_128` adapter, and remove the legacy
  64-bit handle projection and numeric SQLite representation. Preserve the
  checkpoint-2 continuation boundary, keep bridge-only presentation omissions
  separate, perform the coordinated database epoch/reset cut, and delete all
  positive compatibility paths for superseded core-event versions.
- **Regression watch:** Whole-batch malformed-event rejection, cursor
  immutability, Gap recovery, Progress identity/monotonicity, terminal
  precedence, history audit degradation, Boolean-as-integer mistakes, unsafe-
  number or narrowed-file-identity leakage, reachable logical-byte/timestamp
  refusal, and stale development databases.
- **Tests:** At the first stop, prove production dispatch and persistence stay
  exact-v4, no production route can select v5, and the directly addressed v5
  consumer/validator helpers accept and reject the exact target. At the second,
  run Core,
  executor, verifier, database, workflows, dispatcher, and interfaces
  departments; strict codec/payload round trips and wrong-version refusal;
  every detail/reason/review-limit population/axis variant, key, nullability,
  cardinality, and signed-64 bound; plan logical-byte refusal and scanner
  scalar-warning behavior; full-width `FileIndex128` codec/database round trips;
  shared native-identity adapter use by scanner, preflight, executor, and
  verifier; NTFS/ReFS equivalence witnesses for any retained `st_ino` fast path;
  values above signed 64-bit and unsigned 64-bit in test doubles; absence of
  legacy high/low narrowing and numeric file-index storage; exact refused/unrun
  review-limit invariants, `TerminalSummary` copy, history all-null-or-exact
  group, terminal hash/repeated-finalization/reconstruction/CLI parity, and
  absence of presentation omissions from history; arbitrary-object/raw-int
  rejection; diagnostic omission without truncation and checked core-versus-
  presentation witness separation; exact maximum reliable envelope accepted
  plus one structurally over-limit rejection before sequence/queue mutation;
  maximum head drained alone under the bridge ceiling; duplicate-key and scalar
  corpora; startup/CLI reset guidance; required Node validator/reducer;
  ordinary suite; current-source v5 event/custody drift runs. At the final stop,
  prove source/fixtures contain no positive v3/v4 compatibility and repeat the
  ordinary suite plus the settlement oracle. Frozen old measurement artifacts
  remain untouched historical evidence.
- **Docs/review:** Mark v5 active in CORE, DATABASE, HISTORY, TESTS, M1_BRIDGE, INTERFACES, and README. Repeat the settlement oracle three times and independently inspect removal completeness.

### 3R. Remediate independent checkpoint-review findings

Checkpoint 3.3 is blocked until the authorized remediation sequence closes and
Reviewer S5 has a user-approved disposition: an implemented design or an
explicitly accepted deferral/residual recorded in its owning authorities. The
findings were reported after checkpoints 1–3.2 had already landed, so this
sequence repairs those delivered boundaries without folding the work into the
legacy-removal commit or changing checkpoints 4–12.

Every row below is a separately reviewed and committed checkpoint. One builder
implements only that row, runs its declared focused and departmental gates,
and presents the exact diff to a reviewer who did not build it. The reviewer
checks requirement drift, fault combinations, security consequences, test
authority, and unnecessary scope. Findings are corrected and the affected
gates rerun before the row is committed. Review the staged snapshot and run
`git diff --cached --check` immediately before every commit; do not carry a
partly implemented later row into that snapshot. Matching component docs and
causal `BUGS.md` entries travel with the behavior they describe. At every safe
stop, replace HANDOFF's operational sections with the completed row, exact
verification, dirty-file ownership, and next command; retain the appended raw
review reports as the active finding source through this sequence. The final
row reconciles cross-cutting status, changelog, and integrated evidence.

Finding ownership is exact at the aspect level:

| Finding or finding aspect | Owning row |
| --- | --- |
| F1, F4, F7, S2 | 3R.4 prerequisite-cause settlement |
| F2, F3, F10, S3, S7 reducer-matrix gap | 3R.1 settlement gate |
| F6, S7 payload closed-set/contradiction gaps | 3R.2 continuation codec gate |
| F5, S4, the first three post-F7 behavior notes | 3R.6 compound workflow failure |
| Post-F7 canceled-settlement assignment note | 3R.6 direct dataflow check; remove only if it is still dead |
| F8, F9 | 3R.11 private seam and source gates |
| F11, S8 | 3R.15 documentation closure |
| F12 production Python-view validation | 3R.10 live task-update boundary |
| F12 logical-byte Node corpus | 3R.9 timestamp/reliable-size corpus |
| F12 Python-to-JavaScript witness binding | 3R.11 source/differential gate |
| F13, S16 | 3R.14 file-identity codecs |
| F14 | 3R.7 scalar/file-id boundary |
| S1 | 3R.3 retained committed settlement |
| S5 | explicit design hold; no implementation row |
| S6 | 3R.5 diagnostic containment |
| S9, S13 | 3R.10 live task-update/custody boundary |
| S10, S11 | 3R.8 exact event operation truth |
| S12, S17 | 3R.9 timestamp/reliable-size boundary |
| S14 topology authority and direct tests | 3R.12 dormant database authority |
| S14 production admission and S15 | 3R.13 WAL-aware database activation |
| S18 positive v4 task-view fixtures | 3R.10 live task-update boundary |
| S18 contradictory recording/cancellation corpora | 3R.8 operation truth |
| S18 timestamp/size/logical-byte Node corpora | 3R.9 timestamp/size boundary |
| S18 legacy Progress/vocabulary/live-route gates | 3R.11 source gates |
| S18 active-document drift | 3R.15 documentation closure |

#### 3R.0 Ratify the remediation sequence

Commit: `docs: plan independent checkpoint remediation`

- **Acceptance:** Freeze this order and the aspect-level ownership map above,
  preserve checkpoint 3.2 as the active runtime, and keep checkpoint 3.3
  unstarted.
- **Tests/review:** Finding-map completeness, active-plan consistency,
  documentation links, `git diff --check`, and independent plan review.

#### 3R.1 Restore settlement-gate authority

Commit: `test(executor): restore settlement gate authority`

- **Findings:** F2, F3, F10, S3, and S7's reducer-matrix gap.
- **Acceptance:** The settlement oracle reads the authoritative production
  `ExecutionSet.recording_reasons` and `recording_issues` through a typed
  oracle-only side channel; its exact seven-case attribution catalog fails
  closed and is manifest-protected. Keep the historical event-v4 normalized
  trace adapter explicit, and leave the protected scenario/row manifest,
  normalized trace, baseline JSON, and semantic hash byte-for-byte unchanged.
  Restore both directions of the reducer matrix assertion.
- **Tests/review:** Focused executor/tool tests; tools and executor departments;
  three-run settlement check; baseline/hash comparison; explicit TOOLS
  documentation of authoritative typed truth versus the frozen historical trace
  adapter; and an independent gate-authority review.

#### 3R.2 Pin the execution-v6 recording codec

Commit: `test(workflows): pin recording continuation codec`

- **Findings:** F6 and S7's payload closed-set/contradiction gaps.
- **Acceptance:** Pin literal sets of exactly three item reasons and five task
  reasons independently of encoder/decoder enum iteration. Reject every unknown
  raw execution-v6 reason and directly reject the redundant aggregate-versus-
  attribution contradiction. Do not change a production codec in this test-
  authority checkpoint unless a counterexample exposes a separate policy bug.
- **Tests/review:** Focused payload tests, workflows department, exact raw-JSON
  counterexamples, and independent closed-vocabulary review.

#### 3R.3 Retain committed settlement across reliable-sink failure

Commit: `fix: preserve committed settlement across sink failure`

- **Findings:** S1.
- **Acceptance:** Retain the complete pending typed settlement, including a
  committed recorder receipt, before reliable emission without prematurely
  marking continuation status settled. A one-shot sink rejection retries the
  retained settlement through the backstop, never records twice, preserves the
  successful filesystem and recording truth, and still propagates the original
  sink failure. If the item sink rejects every attempt, journal retirement and
  `ExecutionSet.status` remain pending because reliable delivery never
  succeeded; no item enters the accepted-item accumulator or terminal result.
  The durable recorder row/receipt remains immutable and ledger-observable, no
  false failed/unrecorded replacement is emitted, and the task terminalizes as
  failed by the original sink error using only accepted items. This preserves
  receipt finality without inventing a new result or exception contract.
- **Tests/review:** Exact one-shot and persistently rejecting COPY
  counterexamples plus non-byte coverage where the shared path requires it;
  assert the one-shot accepted item, persistent-case immutable ledger receipt,
  pending execution status, absence of a contradictory replacement item, and
  failed accepted-items-only terminal result; executor/workflows/dispatcher
  departments; ordinary suite; three-run settlement oracle; and independent
  journal/terminal-ordering review.

#### 3R.4 Retain prerequisite recording cause through settlement

Commit: `fix(executor): retain prerequisite recording cause`

- **Findings:** F1, F4, F7, and S2.
- **Acceptance:** Make `recording-prerequisite-failed` typed operation-local
  retained state rather than a dynamic exception attribute. Preserve it across
  retry, cleanup-error substitution, backstop exception choice, and durable-
  effect reduction while keeping filesystem settlement precedence unchanged.
  If the same operation also has a reducer-proven unrecorded durable mutation,
  `unrecorded-mutation` takes precedence; otherwise the terminal prerequisite
  refusal remains `recording-prerequisite-failed`. Centralize that precedence
  and only then remove the reducer-disagreement branch made unreachable by the
  closed two-reason composition.
- **Tests/review:** The exact flush-refusal-plus-cleanup-failure and retained-
  UPDATE-retry counterexamples, a combined prerequisite-plus-unrecorded-
  mutation case, executor department, three-run oracle, updated EXECUTOR
  documentation/bug record, and independent retry/reducer review.

#### 3R.5 Contain recording-diagnostic failures

Commit: `fix(executor): contain recording diagnostic failures`

- **Findings:** S6.
- **Acceptance:** Record the typed item/task cause before optional diagnostic
  rendering. If `str(error)` or logical rendering fails, retain `detail=None`,
  preserve the primary recorder/filesystem error, and never leave the recording
  axis clean. Apply the same boundary in executor and workflow recording paths.
- **Tests/review:** Hostile-`__str__` item/final-flush/open/finish/close cases as
  applicable, executor/workflows departments, ordinary suite, three-run oracle,
  owning docs and bug record, and independent exception-precedence review.

#### 3R.6 Preserve recording truth on compound workflow failure

Commit: `fix(workflows): preserve recording truth on compound failure`

- **Findings:** F5, S4, and the behavior notes following F7.
- **Acceptance:** An exclusion-item sink failure combined with recording-close
  failure produces one terminal failed result derived from the live
  continuation, including `recording-close-failed`, before terminal payload
  scrubbing. Remove the circular guard that compares two projections of the
  same `ExecutionSet.recording` value. Retain and document the three ratified
  behavior notes: recording-open containment on an already-failing path,
  verify-present close attribution, and unconditional exit-failure
  preservation. Recheck the reported canceled-settlement assignment against
  current dataflow and remove it only if no consumer remains.
- **Tests/review:** Exact compound counterexample, workflow/core-session/
  dispatcher neighborhood, ordinary suite, three-run oracle, owning docs and
  bug record, and independent terminalization review.

#### 3R.7 Normalize scalar and file-id boundaries

Commit: `fix(core): normalize scalar identity boundaries`

- **Findings:** F14.
- **Acceptance:** Wrong runtime type raises `TypeError`; a grammar-invalid
  string raises `ValueError`; `Scalar64` overflow raises `ScalarDomainError`;
  and `FileIndex128` overflow raises `ValueError`. Replace the mathematically
  guaranteed `FILE_ID_128` byte-range assertion with construction that needs no
  optimization-sensitive guard.
- **Tests/review:** Wrong-type, malformed-text, exact-bound, and plus-one cases;
  optimized-mode file-id decoding; core, database, and workflows departments;
  ordinary suite; owning docs and causal bug record; and independent scalar-
  boundary review.

#### 3R.8 Enforce exact event-v5 operation truth

Commit: `fix(protocol): enforce exact v5 operation truth`

- **Findings:** S10, S11, and the contradictory-recording/cancellation portion
  of S18.
- **Acceptance:** One filesystem-outcome/recording-reason matrix governs
  `ItemOutcome`, Python envelope/view validation, and packaged JavaScript.
  `TerminalSummary`, Python validators, JavaScript terminal/result validators,
  and `OperationResult` enforce the same compound and execute-cancellation
  invariants.
- **Tests/review:** Complete valid/invalid axis matrix, both cancellation
  counterexamples, required Node corpus, core, executor, workflows, database
  (including history), and interfaces departments, ordinary suite, owning docs/
  bug records, and independent Python/JavaScript differential review.

#### 3R.9 Align timestamp and reliable-size boundaries

Commit: `fix(protocol): align v5 timestamp and size boundaries`

- **Findings:** S12, S17, F12's logical-byte corpus gap, and the timestamp/size/
  logical-byte corpus portion of S18.
- **Acceptance:** Freeze the service grammar to a four-digit calendar date,
  literal `T`, two-digit hour/minute/second, either no fraction or exactly six
  fractional ASCII digits, and the literal UTC suffix `+00:00`; calendar fields
  must construct a real Python datetime, so basic/week/date-only/24:00 forms,
  impossible dates, `Z`, and other offsets refuse. Apply that grammar identically
  in Python and JavaScript. Python `SessionEventView` and JavaScript reliable-
  event validation reconstruct the canonical persistence envelope and enforce
  the 1,048,576-byte ceiling on reliable events before cursor, queue, reducer,
  or callback mutation.
- **Tests/review:** One shared timestamp corpus, exact-maximum and plus-one
  public-view witnesses in Python and Node, logical-byte review facts in the
  Node corpus, core, workflows, and interfaces departments, ordinary suite,
  owning docs/bug records, and independent grammar/byte-accounting review.

#### 3R.10 Validate exact task updates before custody release

Commit: `fix(web): validate task updates before custody release`

- **Findings:** F12's production Python-view boundary, S9, S13, and S18's
  positive-v4 task-view fixtures.
- **Acceptance:** Validate every offered, recovered, drained, and command-
  returned task update through the exact v5 Python view contract before queue,
  cursor, terminal-delivered, serialization, or release mutation. A terminal
  record requires a non-null valid result whose terminal state agrees; a
  result-free or malformed collaborator record never releases custody.
  Packaged JavaScript applies the same terminal-record rule.
- **Tests/review:** Replace positive v4 adapter fixtures, prove rejected batches
  leave queue/cursor/custody unchanged, exercise result-bearing release and
  result-free refusal, interfaces/workflows departments and ordinary suite,
  owning docs/bug records, and independent custody/mutation-order review.

#### 3R.11 Harden exact-v5 seam and source gates

Commit: `fix(web): harden exact-v5 source gates`

- **Findings:** F8, F9, F12's Python-to-JavaScript witness gap, and S18's legacy
  Progress/vocabulary/live-route gate gaps.
- **Acceptance:** Freeze the private legacy browser seam to literal version 4,
  slice only the actual live validator in routing tests, inspect the active v5
  Progress validator and complete v5 vocabulary, and run production Python
  public witnesses through the packaged JavaScript consumer. The checkpoint is
  gate/test hardening; it does not widen the private compatibility seam or
  activate a new production route.
- **Tests/review:** Static mutation-resistant source gates, production-view-to-
  Node differential corpus, interfaces department, ordinary suite, matching
  INTERFACES documentation, and independent gate review.

#### 3R.12 Pin exact database topology authority

Commit: `refactor(database): prepare exact schema topology validation`

- **Findings:** S14's topology authority and direct-test portion.
- **Acceptance:** Add one exact comparator for the complete current user
  schema—tables, columns, constraints, indexes, triggers, and definitions—and
  direct tests for marker-only, missing-object, extra/poisoned-object, and
  definition drift. Only declared SQLite-owned statistics artifacts are exempt.
  Keep the comparator dormant: no reader, initializer, repository, or pair gate
  selects it yet, so this preparatory safe stop does not claim production S14
  closure or change WAL behavior.
- **Tests/review:** Direct complete-v4/v6 and malformed-topology matrices,
  database department, proof that production callers remain unchanged, and
  independent schema-canonicalization review.

#### 3R.13 Activate complete WAL-aware database admission

Commit: `fix(database): validate complete pairs without mutation`

- **Findings:** S14's production boundary and S15.
- **Acceptance:** Ledger/history readers and initializers select 3R.12's exact
  topology authority before any `CREATE IF NOT EXISTS` repair. Sidecar-free
  databases retain the direct immutable read. Any `-journal` presence refuses
  before opening a source database; NamiSync neither guesses whether it is hot
  nor performs rollback recovery during admission. A WAL-bearing database is
  validated from a private recovery snapshot that sees committed marker and
  topology truth without opening or creating source SHM authority. The
  validator never mutates source main/WAL/SHM/journal artifacts; quiescent ready,
  refusal, and error fixtures remain byte-for-byte identical. An injected or
  concurrent source drift refuses closed, and the drift fixture attributes only
  that external change with no additional validator mutation. Repository and
  initializer entry points use the same preflight before an ordinary SQLite
  open can mutate refused source artifacts. Do not invent a new database-size
  acceptance wall.
- **Tests/review:** Complete current reopen, marker-only/poisoned current files,
  main-plus-journal and orphan-journal refusal, journal drift/no-validator-
  mutation, wrong WAL marker, missing SHM, benign live WAL, WAL topology poison,
  snapshot drift/failure, repository/initializer no-mutation cases, database
  department and ordinary suite, updated DATABASE docs/bug records, and
  independent schema/TOCTOU/temp-ownership review.

#### 3R.14 Keep file identity textual in generic JSON

Commit: `fix(identity): encode FileIndex128 as canonical JSON text`

- **Findings:** F13 and S16.
- **Acceptance:** Core plan serialization/fingerprinting and recorder
  idempotency hashing recognize `FileIdentity` before generic dataclass descent
  and emit canonical quoted `FileIndex128`; unrelated integers stay numeric.
  Preserve and explicitly pin the existing low-32-bit uppercase volume-serial
  normalization that makes `FILE_ID_INFO` evidence comparable with
  `GetVolumeInformationW` `VolumeId`; it is separate from the full 128-bit file
  index. Trace every persisted fingerprint/idempotency consumer and record an
  explicit compatibility conclusion before implementation. If an existing
  checkpoint-3.2 hash can be revalidated or replayed under the same current
  markers with different semantics, stop for a coordinated epoch/reset
  decision rather than silently changing that durable contract.
- **Tests/review:** Exact maximum file index through nested plans/inventory/
  evidence and recorder hashes, an ordinary nested-dataclass integer that must
  remain a JSON number, deterministic fingerprint coverage, exact persisted-
  consumer compatibility evidence, and an old-current-marker numeric-
  fingerprint execution-v6 continuation decoded and re-fingerprinted by new
  workflow code. Run core, planner, database, and workflows departments plus
  the ordinary suite; update owning docs/bug record; and obtain independent
  codec-compatibility review.

#### 3R.15 Reconcile remediation evidence and active documentation

Commit: `docs: reconcile independent checkpoint remediation`

- **Findings:** F11, S8, and S18's active-document/status drift.
- **Acceptance:** Reconcile M1_SHELL, M1_BRIDGE, DATABASE, ARCHITECTURE, CORE,
  TESTS, component documents, README, CHANGELOG, BUGS, and HANDOFF with the
  delivered behavior and exact safe stop. Remove stale active-v4/history-v5/
  checkpoint status claims without rewriting historical evidence. Require and
  record the user-approved S5 disposition before this row can complete; an
  accepted deferral keeps an open causal BUGS entry, a DEFENSE residual/model-
  reopen disposition, truthful noncategorical DISPATCHER wording, and exact
  HANDOFF status. Migrate lasting causal dispositions and evidence from the raw
  review reports into BUGS, CHANGELOG, and owning documents. A completed 3R.15
  always replaces HANDOFF in full without the raw appendices; an intermediate
  safe stop retains them only while 3R.15 remains incomplete. Keep checkpoint
  3.3 unstarted and the private decoder seam intact.
- **Tests/review:** All affected departments, ordinary suite with required
  bundled Node, import architecture, three-run settlement oracle, exact source
  scans, `git diff --check`, and final independent requirement/security review.

**Design hold — not authorized by this sequence:** Reviewer S5 identifies a
failed terminal store write that can leave an older continuation-bearing row in
an arbitrary `SessionStore`. The current `put/load_all/drop` protocol cannot
guarantee scrubbing after its mutator rejects the scrubbed record, and a best-
effort `drop` would not make that guarantee true. Resolving it requires an
explicit storage design: keep continuation bytes solely under dispatcher-owned
process memory and persist only redacted records; add a stronger atomic storage
contract; or introduce separately revocable protected continuation storage.
Do not change this boundary without a user decision; absent that decision,
3R.15 and checkpoint 3.3 remain blocked after all authorized fixes land.

### 4. Install task-centric lifecycle and compact artifacts

Commits, in order:

1. `test(web): pin task artifact reservation model`
2. `feat(web): install dormant task lifecycle`
3. `feat(web): retain multi-session task artifacts`

- **Objective:** Remove the one-session assumption before adding production surfaces.
- **Position and safe stops:** The first commit freezes the complete analytical
  artifact graph, per-artifact constants, aggregate formula, maximum fixtures,
  independent validator, and typed reservation/refusal expectations before any
  result is measured or surface is reachable. The second installs the task
  registry, ownership/lifecycle machinery, bounded artifacts, and dormant UI
  consumers while the production nine-row command map and current one-session
  behavior remain exact. The third is the activation/closure commit: it
  switches the command map to the exact 12 rows, removes replaced aliases,
  exposes the coherent task rail and controls, and proves the predeclared model
  without changing its constants. Any defect in that model follows the
  checkpoint execution protocol and restarts its evidence; it is never folded
  into the activation commit by amendment.
- **Acceptance:** Implement the mapped one-current-session task model,
  lifecycle and result authorities, owner claim, transactional observation
  attachment, task reads/control, exact-session release, task close, compact
  overlays/results, bounded terminal summaries, and page rehydration. Apply the
  exact publication and overlay invariants from `M1_BRIDGE.md`, and enforce the
  complete conservative pre-surface reservation floor from `DEFENSE.md` §1.3;
  checkpoint 11 calibrates and proves that already-active containment model.
  Revise the production command mapping from nine to 12 unique rows: retain the
  four bootstrap/cosmetic and two current Setup rows while replacing three
  current task/session rows with the six checkpoint-4 task rows.
- **Regression watch:** No task lock across facade, JSON, database, or filesystem work; non-atomic issue/retirement classification and lease acquisition; normal named publication advancing the task epoch; same-revision start/start, control/start, control/close, start/close, and release/successor races; claim-owner and attach/start compensation; terminal-event versus terminal-record race; stale drain/release; pinned-generation release or eviction; observer-thread and close-long-poll deadlock; receipts released before task close; references retaining full results; uncharged read/native/callback copies; capacity failure during release/close; mutation rows accidentally taking the lifecycle claim.
- **Tests:** At the first stop, prove the independent validator rejects every
  constant, formula, root-class, and refusal-boundary drift before retaining
  evidence. At the second, prove the exact current nine-row production map and
  one-session behavior remain reachable while every new task command and
  rendered control is unreachable. At activation, run the dispatcher/
  interfaces/service neighborhood; competing starts and
  unpublished-task claims; control/start/close/release interleavings; atomic
  lookup, issue, retirement, claim, lease, and epoch decisions; publication-
  versus-close barriers; exact overlay/result revision invariants; no mixing of
  plan, execution, inventory, integrity, or post-copy generations; every
  bridge/defense-owned population and retention refusal boundary; old/new
  diagnostic and artifact overlap; pinned-generation replacement/eviction;
  handler-saturation reconciliation; start/control/release/close replay and
  tombstones; byte-aware drain; reinjection; delayed terminal cleanup; and
  shutdown during observation. Python and JavaScript policy mirrors freeze the
  exact 12-row mapping with no retained alias for a replaced task/session row.
- **Docs/review:** Update ARCHITECTURE, M1_BRIDGE, DESKTOP_UI, INTERFACES, and DISPATCHER. Review the complete ownership graph and initial BR-G-45 analytical model; land the checkpoint-4 BR-G-32 command-table and BR-G-46 command-map revisions together.

### 5. Unify probing, recents, and typed directory admission

Commit: `feat(workflows): unify location probing and recent locations`

- **Objective:** Give Setup and inventory one workflow-owned location-candidate pipeline.
- **Acceptance:** Add `LocationCandidate`, typed probe states, fresh binding resolution, the exact supported-volume predicate, bounded ledger recent queries, deterministic indexes, process-secret HMAC recent ids with current-top-five/active-mapping revalidation, and common picker/typed/recent admission. Existing inventory binding uses the shared workflow without weakening scanner/preflight/executor re-probes.
- **Regression watch:** Accidental `abspath` of relative input, reparse following, UNC/mapped-network admission, stale mount hints, clone ambiguity, probing that enumerates children, raw path/exception leakage, and treating `RootAuthority` as cached authorization.
- **Tests:** Core/database/workflow/interface neighborhood; every parser rejection class; file-leaf rejection; long/slash paths; root/leaf reparse and placeholder; missing/offline/remount/ambiguous volume; five/five/five query bounds and `EXPLAIN QUERY PLAN`; activation races, slot expiry, and purpose mismatch.
- **Docs/review:** Update DEFENSE, ARCHITECTURE, DATABASE, INVENTORY, WORKFLOWS, and FEATURES. Perform an adversarial parser and TOCTOU review.

### 6. Build frozen Setup and serial multi-pair creation

Commit: `feat(web): add frozen setup and serial task creation`

- **Objective:** Deliver the initial Setup page and exact Setup bridge rows.
- **Acceptance:** Render typed/picker fields, probed recents/pairs, all implemented semantic controls, disabled ADS, raw bounded inputs admitted to backend-canonical complete snapshots, immediate path invalidation, admission freeze, truthful slotless partial-pair refusal, standalone inventory-task creation, and serial best-effort pair creation. Add explicit Plan again through `activate_task_pair` followed by ordinary `start_plan`: resolve the retained plan's reviewed volume identities, publish two slots only when both accept, reuse its frozen Setup options, and create a new default-selection task without background replanning or authorization carry-forward. No Setup edit writes global defaults and JavaScript owns no filter normalization. Replace the two current Setup rows with the eight checkpoint-6 rows, producing 18 unique commands with the six checkpoint-4 and four retained bootstrap/cosmetic rows.
- **Regression watch:** Default-settings race, hidden `null` fallback, filter amplification, stale slots, drive-letter reuse, task close or plan-generation change during reviewed-pair resolution, display text promoted to path authority, double click, command-ID reuse after edits, automatic retry with a new ID, background task creation, selection carry-forward, partial pair activation, navigation/reinjection, and unsafe filesystem labels in the DOM.
- **Tests:** Exact 18-row Python/JS command policy mirrors and key validators; filter bounds/canonicalization; mixed batch successes/refusals; exact `slot-claimed` busy guidance; one-slot and atomic two-slot `slot_capacity_full` under all/partially pinned capacity with no native probing or partial slot; `recent_unavailable`; task-pair resolved/remounted/missing/offline/ambiguous identities; exact replay before and after task close; plan-generation and slot-expiry races; lost response both before and after task publication, with post-publication lookup using the bounded route rather than expired/consumed slots; document replacement; admitted-task recovery; settings fingerprint/commitment; headed typed/paste/picker/recent/Plan-again flows and hostile text.
- **Docs/review:** Update DESKTOP_UI, M1_BRIDGE, M1_SHELL, FEATURES, and INTERFACES. Close BR-G-47 only after headed evidence and parser review; land BR-G-32's checkpoint-6 exact-table revision and close BR-G-46's reopened command-map clause only after that revision passes.

### 7. Deliver bounded plan review and execution admission

Commit: `feat(web): add bounded plan review and selection`

- **Objective:** Complete the Slice 5 plan/review half.
- **Acceptance:** Implement the bridge-owned bounded plan projection, view,
  window, anchor/detail, selection, review-header, notice, overlay, and move-peer
  contracts. Project each immutable operation exactly once, preserve
  path-versus-member authority for same-target groups, and keep selection,
  rollups, counts, risk, and action scope independent of filters and windows.
  Review-time facts remain context; every committed nonempty current selection
  attaches and fresh-preflights after authority/confirmation checks. Publish a
  complete bounded plan and notice generation or no new artifact, preserving
  the prior complete plan where the mapped replacement policy requires it. Keep
  selection frozen while an attempt starts or runs; submission failure and a
  terminal unrun result return it to reviewing with one revision advance, while
  the first ran result freezes it permanently. A retry uses a fresh start command
  and commitment; replay of the old command returns only its original attempt.
  At this checkpoint's closure, an execution started from the plan remains
  usable through checkpoint 4's task rail, generic live state, pause/resume/
  cancel controls, bounded terminal summary, and an action-guiding generic
  "Execution did not start" state that returns an unrun selection to review.
  Rich item overlays and ledger evidence remain checkpoint 8 work. If that
  complete generic path is not available, keep both the `start_execution` row
  and rendered Execute gesture dormant until checkpoint 8 rather than expose a
  blind execution start.
- **Regression watch:** Rebuilding trees per window, operation-scaled responses, client-derived hierarchy/domain status, filter-dependent selection, synthetic ancestors, move annotations, stale selection/view revisions, double execution, failed or terminal-unrun admission leaving selection frozen, reopening without a revision advance, stale pre-commit mutation after reopening, replay creating a second authorization, and treating zero-byte ran work as unrun.
- **Tests:** Planner/workflow/interface neighborhood and the exact BR-G plan
  fixtures/boundaries in `M1_BRIDGE.md`; first-excess/no-partial publication;
  review-header rehydration and revision guards; capacity fact availability;
  reviewed-versus-fresh preflight behavior; typed notice merge, omission, and
  action exclusion; same-target grouping and exactly-once operation projection;
  folder/group selection and rollups; stale/replayed mutations; submission-
  failure and terminal-unrun revision transitions; edited-subset execution-
  refusal retry with a new commitment; permanent freeze at the first ran result;
  checkpoint-4 task-rail/live/control/terminal usability before checkpoint 8;
  search/filter/facet/window/dependency boundaries; move-peer
  positive and suppression cases; off-window follow; destructive confirmation;
  hostile DOM; latency/memory; and headed production witnesses.
- **Docs/review:** Update PLANNER, WORKFLOWS, M1_BRIDGE, M1_SHELL, and DESKTOP_UI. Close BR-G-15, BR-G-35, BR-G-37, plan BR-G-32, and the plan portion of BR-G-42 after adversarial selection/reopening review.

### 8. Deliver execution review and ledger-current evidence

Commit: `feat(web): add execution review and ledger evidence`

- **Objective:** Complete live execution, retained review, and trustworthy full-hash display.
- **Acceptance:** Attach execution atomically; render v5 progress, pause/resume/cancel, indexed follow, terminal axes, item/task recording issues, and retained file-list windows whose plan rows carry an exact `ExecutionOverlay` while leaving the separate post-copy overlay untouched. Render `filesystem="refused"` plus `disposition="unrun"` as the generic “Execution did not start” review state with reopened selection controls; do not expose preflight terminology or infer a cause from those axes alone. Add one batched transactional operation/run/inventory evidence query and bounded per-item detail including the item omission witness.
- **Regression watch:** Live-versus-terminal overlay disagreement, Gap loss, later task failure suppressing earlier evidence, unrecorded item borrowing another inventory hash, N+1 queries, canonical target collisions, latest-writer confusion, diagnostic amplification, and premature session release.
- **Tests:** Executor/database/workflow/interface neighborhood; all filesystem/
  recording combinations; exact overlay invariants; separate omission axes;
  committed item followed by later task/audit failure; scope match/change/
  invalidation/missing; full digest and no plan hash; Gap-plus-terminal
  reconciliation; generic refused-filesystem/unrun messaging and reopened-
  control revision;
  navigate away/back; the bridge-owned maximum result overlay;
  and post-copy replacement leaving execution byte-identical.
- **Docs/review:** Update EXECUTOR, RECORDER, DATABASE, WORKFLOWS, INTERFACES, M1_BRIDGE, and DESKTOP_UI. Close the execution portion of BR-G-36 and relevant BR-G-48 cases after executor and bridge reviews.

### 9. Deliver inventory projections and current evidence

Commit: `feat(web): add inventory projections and evidence`

- **Objective:** Complete the Slice 6 inventory surface.
- **Acceptance:** Implement the bridge-owned bounded inventory projection,
  location/completeness view, search/filter/collapse, windows, warnings, rollups,
  details, actions, revisions, and omission witnesses. Build the domain tree
  before informational warnings, keep warnings outside path/action scope, and
  publish a complete bounded generation or preserve the prior complete refresh
  generation. Keep ledger verification and ordinary-integrity overlays
  independent, show overflow rather than clamp it, label current hash/time
  evidence truthfully, and return typed admission/action refusals.
- **Regression watch:** Full-location reload per window, stale `view_id`/row ID, patch/rebuild races, acknowledgment count drift, hidden rows changing rollups, LRU eviction deleting task identity, unsafe SQLite integers, and treating a stale hash as current.
- **Tests:** Database/workflow/verifier/interface neighborhood and the exact
  BR-G inventory fixtures/boundaries in `M1_BRIDGE.md`; first-excess/no-partial
  publication and refresh preservation; cache pin/evict/refusal; location and
  revision shapes; concurrent projection/result replacement; search/filter/
  hiding counts; rollup overflow; paging; recursive scope and warning-detail
  refusal; diagnostic omission and stable warning identities; domain/action
  isolation; independent ledger/integrity overlays; hash provenance; scalar
  boundary/display; memory/latency; and hostile DOM witnesses.
- **Docs/review:** Update INVENTORY, DATABASE, M1_BRIDGE, M1_SHELL, and DESKTOP_UI. Close BR-G-22, BR-G-23, BR-G-38, inventory BR-G-32, inventory BR-G-42, and the inventory portion of BR-G-39 after projection-race review.

### 10. Deliver integrity and deferred post-copy verification

Commit: `feat(web): add integrity and post-copy verification`

- **Objective:** Complete integrity controls and same-task manual verification without persistent operation-time hashes.
- **Acceptance:** Add baseline/verify/rebaseline actions and a distinct no-rescan post-copy workflow. `start_integrity` carries receipted `current_evidence_acknowledged:boolean`, required true exactly for rebaseline and false for baseline/verify; every other combination is invalid before claim, scope resolution, ledger, or native work. Automatic linked verification remains the original compound session using transient evidence. Ordinary integrity publishes only the inventory row's `integrity_outcome` overlay; manual exact verification publishes only the plan row's separate `post_copy` overlay, and neither overwrites current ledger state or execution. Each manual exact attempt attaches a new dispatcher/history session identity and conditionally reads/writes against the original execution `runs.run_token`; it neither opens a new ledger scope nor reuses an earlier history identity. Under the owner claim, start first performs the atomic handoff classification and returns blocked/all-already-verified without native probing; only a ready subset triggers fresh target admission, followed by one final atomic classification that either freezes the still-ready rows or returns the new assessment. A failed, canceled, or partial attempt may be retried for the newly ready remainder, atomically replacing only the task's prior post-copy result/overlay after the old/new overlap is reserved. A race returns exact conflict, the five typed `ready`/`already_verified`/`eligible_incomplete`/`unrecorded`/`superseded` counts plus reason, or typed candidate refusal without inventing a task/view/count.
- **Handoff policy:** Every applicable selected byte-producing operation must have a filesystem-successful terminal outcome, but unrelated non-byte-operation failure does not falsify a copied file's evidence and aggregate recording may be degraded. The five counts partition applicable selected byte-producing work; failed, canceled, or unreached work increments `eligible_incomplete`. Same-scope copy evidence is `ready`; same-scope readback/verify evidence with non-null `last_verified_at` is `already-verified` and increments `already_verified`; any incomplete, unrecorded, or superseded applicable item blocks exact admission. `post-settlement-state-diverged` also blocks because execution applicability is no longer trustworthy, regardless of the five counts; final-flush, finish, or close degradation alone remains admissible when every eligible row is committed and current. Positive `ready` with optional already-verified siblings starts only the ready subset; a nonempty all-already-verified set reports that without starting work; absent divergence, all five counts zero blocks as `no-applicable-items`. Otherwise offer ordinary “verify current state,” which may refresh and establish a new scope.
- **Regression watch:** Reusing ordinary `run_integrity()` for exact handoff—it refreshes and destroys scope continuity; classification/admission races; mixing exact and current candidates; canonical target duplicates; stale mount choice; verifier recording degradation; result-ID misalignment; mutation of the original execution result.
- **Tests:** Exact true-rebaseline/false-baseline/false-verify acknowledgement starts and receipt replay; false rebaseline, true baseline/verify, missing, and non-Boolean rejection before claim/scope/ledger/native work; ready, mixed ready/already-verified, all-already-verified, superseded by scan/run/rebaseline, missing/invalidation/unrecorded/offline, failed execution, final-flush-degraded but fully committed execution, last-moment conditional-recording race, pause/resume/cancel followed by a same-scope remaining-subset retry and old/new post-copy reservation, whole-object live replacement over overlapping/disjoint candidate indexes with prior settled membership retained until terminal, projection invalidation-before-outcome, and current-state fallback.
- **Docs/review:** Update VERIFIER, WORKFLOWS, INVENTORY, DATABASE, M1_BRIDGE, and DESKTOP_UI. Close the remaining BR-G-39 and BR-G-48 cases after a dedicated handoff/race review.

### 11. Close early Slice 7 lifecycle and scale

Closure commit: `feat(web): close task lifecycle and retention budgets`

- **Objective:** Prove cleanup, shutdown, and retained-task containment across the completed surfaces.
- **Acceptance:** Calibrate and verify without post-selecting or silently
  changing the checkpoint-4-frozen analytical constants; prove the aggregate
  task guarantee and count wall owned by `DEFENSE.md` §1.3, plus
  reservation/shrink/refusal, live closing, terminal presentation/release
  retry, explicit close, repeated create/release/close, complete response/native/
  browser transients, and concurrent shutdown. Any policy defect lands
  separately, revises the enforced constant before a new run, and resets the
  evidence run. The named commit lands only after any such fix commits and is
  the final evidence/status closure, not the sole allowed commit for checkpoint
  11.
- **Regression watch:** Silent eviction, count-only enforcement, uncharged receipts/string pools/full results/native copies, diagnostic bypass, browser callback copies, blocked close handlers, cleanup before terminal record, task rail reconstructed from dispatcher sessions, and authority surviving declared release points.
- **Tests:** BR-G-41 lifecycle tests; BR-G-45 complete artifact-root and
  aggregate-retention instrumentation, including the accepted maximum handler
  and terminal-reconciler reservations; maximum-task guarantee plus refusal;
  repeated cycles; live/paused/terminal close; delayed terminal at handler
  saturation; issue/close barriers racing readers, durable mutations,
  replacement pins, and `next_events` long-polls; shutdown during starts/drains/
  close; current-source event/custody; plan/inventory scale gates and installed
  headed witnesses.
- **Docs/review:** Update DEFENSE measurement authority, M1_BRIDGE, M1_SHELL, TESTS, INTERFACES, and DESKTOP_UI with predeclared fixtures/budgets and evidence. Close BR-G-41 and BR-G-45 only after independent artifact-graph and shutdown reviews.

### 12. Overall adversarial and documentation sweep

Commit: `docs(gui): close stage 6 surface verification`

- **Objective:** Reconcile the reslice as one system and land any discovered fixes separately before final documentation.
- **Acceptance:** No v3/v4 runtime machinery, dormant bridge rows, operation-time hash persistence, path ingress outside the shared admission workflow, unbounded task/result response, stale documentation, or undeclared task artifact remains.
- **Regression review:** Executor settlement/order; per-item versus task recording truth; stale bridge actions and lost responses; exact request/result keys; origin/readiness/handler-capacity rules; path-parser abuse; unsafe scalars; DOM text/layout safety; projection races; manual-handoff supersession; memory-budget bypass; shutdown and cleanup authority.
- **Tests:** Settlement oracle three identical runs; ordinary `pytest -q`; headed interfaces with cleared default addopts; complete suite with `-o "addopts="`; `lint-imports`; `git diff --check`; installed-wheel v5 bridge and product-DOM gates; every `test_br_g_*` collected with no unsupported skip/xfail; final BR-G-42/45 evidence.
- **Docs/review:** Reconcile ARCHITECTURE, DEFENSE, FEATURES, README, all owning documents, M1_BRIDGE/M1_SHELL gate status, and TESTS. Extend one CHANGELOG task across checkpoints and replace HANDOFF at closure. Use a separate reviewer for the final security, executor, bridge, and requirement-drift audit.

## Explicit deferrals

- History page, history bridge pagination, BR-G-40, history BR-G-42, and SH-G-9.
- Global settings mutation page; Setup only reads defaults and freezes per-task overrides.
- Drag-and-drop and file-scoped planning.
- Geometry, column, durable tree-expansion, and other nonappearance UI-state consumers.
- Human-gesture provenance against compromised trusted JavaScript.
- Desktop task survival across process closure/restart.
- GUI Break 2 cohesion work, release packaging, BR-G-43/44, and SH-G-15.

## Checkpoint 0 audit issue and resolution record

This is the retained review record for the first ratification and
reconciliation round. It is not a separate contract authority. “Accepted
target” means the named implementation checkpoint has not activated the
documented resolution.

### Runtime and cross-contract findings

| Issue or incompatibility | Resolution | State |
| --- | --- | --- |
| Execution preflight could observe selection or review facts that were not the exact committed review authority. | Commit the current nonempty revisioned selection, bind its digest and provenance, rederive it before execution admission, and publish any fresh refusal as execution-attempt truth without rewriting the reviewed plan. | Accepted target, checkpoints 7–8. |
| Plan immutability, selection after an unrun attempt, and selection after consumed execution authority had been collapsed into one permanent freeze. | Keep the plan immutable; return selection to `reviewing` at a new revision after submission failure or a terminal unrun result; freeze selection permanently when the first attempt reports `disposition=ran`. | Accepted target, checkpoints 7–8. |
| An unrun task could need a genuinely new plan, but it had no recent ledger run and its reviewed display path was unsafe to reuse after drive-letter reassignment. | Add identity-resolving `activate_task_pair`; explicit **Plan again** activates two fresh slots and starts a new task with the old frozen setup, default selection, and no copied authorization. | Accepted target, checkpoint 6. |
| User deselection, dependency fallout, and safety exclusion could collapse into one omitted-operation meaning. | Retain canonical `user_deselected` provenance separately, dependency-close only that set, and derive typed excluded outcomes from the reviewed plan plus provenance. | Existing direction retained; desktop admission lands at checkpoint 7. |
| Filesystem success and recording success were conflated, so a recorder failure could misstate durable mutation truth. | Keep filesystem, integrity, recording, and audit axes independent; add item-local recording degradation and ordered task-wide recording issues without rewriting committed filesystem outcomes. | Accepted target, checkpoints 1–3 and 8. |
| Item-local recorder failure and task-wide open/flush/finish/close failure lacked a stable attribution boundary. | Pin the four-way settlement matrix in the oracle, then add sparse typed item attribution and centrally reduced task issues before changing the event wire. | Accepted target; checkpoint 1 oracle work is in progress. |
| Operation-time copy evidence was being treated as if it could become a durable task artifact. | Keep copy attestations transient inside the same live execution continuation; durable evidence comes only from committed ledger facts and never enters retained tasks or JavaScript. | Accepted target, checkpoint 2. |
| Python’s additive v3/v4 compatibility decoder, exact live-v4 JavaScript validator, and canonical history projection accepted different shapes. | Make the current asymmetry explicit only until a coordinated exact event cut; then use one exact event schema and reset the database pair rather than retain a legacy decoder. | Accepted target, checkpoint 3. |
| Ledger, history, event, and evidence epochs could be upgraded independently and leave a mixed readable-looking pair. | Advance them as one coordinated reset boundary; reject old, mixed, markerless, incomplete, or orphan-sidecar pairs before commands with archive/delete guidance and no automatic migration. | Accepted target, checkpoint 3. |
| Byte counts and filesystem timestamps could cross Python, SQLite, JSON, and JavaScript with incompatible integer precision or coercion. | Use one nonnegative signed-64 arithmetic domain, checked accumulation, and canonical decimal bridge representation; keep opaque native file indexes as non-arithmetic text. | Accepted target; exact walls and the reachable-versus-assertion classification live only in Bridge/Defense. |
| Native identity had three incompatible widths: Python `st_ino` could carry 128 bits, executor/verifier handle probes narrowed to 64, and SQLite stored a signed integer. | Use the complete Windows `FILE_ID_128` through one core-owned adapter and canonical `FileIndex128` text in codecs and the reset ledger; retain a stat fast path only behind executable NTFS/ReFS equivalence evidence. | Accepted target, checkpoint 3; exact domain lives in Bridge/Defense. |
| Reachable timestamp and aggregate-logical-byte failures had arithmetic walls but no exact scanner or pre-publication outcome. | Add the path-local scalar scanner warning and the plan/domain `logical-bytes` review-limit witness; reuse existing typed unavailable/unreadable outcomes at later native probes. | Accepted target, checkpoint 3; exact outcomes live in Bridge. |
| Reliable terminal transport could retain or send an unbounded full result collection. | Transport an item-free bounded terminal summary, update compact overlays before queueing, and retain the full terminal result only under dispatcher custody until reconciliation/release. | Accepted target, checkpoints 3–4. |
| The existing one-session desktop model could not retain a reviewed plan and later results while sessions came and went. | Introduce process-live tasks with one current session and separately named bounded plan, execution, inventory, integrity, and post-copy result slots. | Accepted target, checkpoint 4. |
| Concurrent control/start/release/close commands had no single effect owner, so identical retries and competing commands could both progress. | Use one task-operation owner claim with exact-intent replay/join, typed busy/conflict observations, and owner-only publication or compensation. | Accepted target, checkpoint 4. |
| A review candidate could be staged, rejected, or throw after staging and leave partial overlays, indexes, charges, or stale browser state. | Use an exact staged-result matrix, precharged rejection latch, atomic generation publication, complete compensation to prior/null truth, and one sticky task publication issue with fixed recovery guidance. | Accepted target, checkpoint 4. |
| Reads, replacement, projection eviction, and task close could race on mutable task or generation state. | Add checked task publication epochs, ordinary/cleanup leases, immutable generation pins, write-intent drain, and unpinned-only eviction with revision rechecks after outside work. | Accepted target, checkpoints 4 and 11. |
| Terminal callbacks and close could lose reconciliation capacity or release a successor session. | Pre-reserve a terminal reconciler/callback lease, key release to exact task/session identity, and retain bounded release/close tombstones for retry authority. | Accepted target, checkpoint 4. |
| Shutdown or busy close could strand long polls, observers, pins, or cleanup work while reporting the task closed. | Seal admission, wake/cancel long polls, cancel and reconcile the exact session, drain ordinary then cleanup leases, and only then remove the task and materialize its close tombstone. | Accepted target, checkpoints 4 and 11. |
| Task artifacts, projections, receipts, slots, handlers, responses, and tombstones had incomplete or mutually inconsistent containment rules. | Enforce permanent/transient reservations before surface work, bounded task/projection/receipt/slot stores, non-evicting earned retry authority, and analytically charged response/handler copies. | Accepted target, checkpoints 4 and 11; exact walls live in Bridge/Defense. |
| Picker-only slots, typed paths, remembered locations, and real work starts risked using different path grammars or cached root evidence. | Route every path source through one workflow-owned literal local-directory admission service, issue purpose-bound expiring slots, and freshly re-admit roots when work actually starts. | Accepted target, checkpoints 5–6. |
| “Recent folders” could be inferred from typing/picking or persisted as cosmetic UI state, overstating prior successful use. | Derive recents only from eligible ledger activity, keep reachability separate from history, revalidate on activation, and never place recents in `ui-state.json`. | Accepted target, checkpoints 5–6. |
| Mutable defaults or Setup edits could change an already reviewed plan, and multi-pair creation lacked partial-failure semantics. | Freeze the complete task-local option/filter snapshot into planning and commitment; create multiple pairs serially with independent success/refusal and no rollback of admitted tasks. | Accepted target, checkpoint 6. |
| Manual post-copy verification could rescan, reuse stale hashes, overwrite execution truth, or attach evidence from another run. | Classify one ledger-current same-run snapshot by run token and operation identity, freshly admit the target, start only a ready subset, and publish into a separate replaceable post-copy result slot. | Accepted target, checkpoint 10. |
| Large plan/inventory views could build partial artifacts, let the browser own complete lists, or erase the last complete view on a refused replacement. | Build complete bounded server-owned candidates, publish atomically, page/window only immutable projections, preserve a complete predecessor on replacement refusal, and return a typed no-partial initial refusal. | Accepted target, checkpoints 4, 7, and 9. |
| Viewport rows, display paths, warnings, and coincidental hashes could be promoted into selection, action, or evidence authority. | Resolve opaque ids and recursive scopes server-side, keep warnings non-actionable, keep paths display-only, and label evidence provenance/currentness explicitly. | Accepted target, checkpoints 7–10. |

### Ratification and publication defects found during review

| Defect | Resolution applied during checkpoint 0 |
| --- | --- |
| Signed-64, terminal-summary, task-claim, epoch, and retention decisions were copied through many component documents, creating parallel truths. | Exact protocol shapes now live in `M1_BRIDGE.md`, exact defense walls in `DEFENSE.md`, and component documents carry only local consequences or pointers. |
| The first enlarged Bridge section was disconnected from the DR-BR records and tried to win conflicts through a blanket precedence sentence. | The Bridge map now assigns every shared register area to explicit DR-BR owners and acts as the sole supersession inventory; unmapped decisions remain untouched and targets remain inactive until their checkpoints. |
| `TESTS.md` duplicated checkpoint, module, command, and case catalogs despite the executable department manifest. | It was nearly reverted and now contains only generic accepted-target routing; `tests/_departments.py`, H2 checkpoint clauses, and owning BR-G gates remain the relevant authorities. |
| `FEATURES.md` carried transport schemas, algorithms, limits, and lifecycle implementation detail instead of product behavior. | It now states user-visible active/unrealized behavior and points technical mechanics to Bridge, Defense, or the owning component document. |
| The exact `mutate_selection` row returned only a revision while local DR prose also promised a selection digest. | The response promise was removed; the digest remains internal commitment authority. |
| Publication-fault prose referred to a fixed “message above” that condensation had deleted. | The exact action-guiding close-and-retry message was restored at the publication contract. |
| Register ownership omitted the history/data-epoch owner, over-assigned history pagination to unrelated result/command registers, and missed newly required BR-G traceability. | Map ownership was narrowed and enumerated; epoch ownership and DR-to-gate rows were reconciled, including recording, retention, location, and command gates. |
| The Setup checkpoint required exact slot-claim guidance, but Bridge retained only the tagged busy result. | Exact wait/reselect renderer guidance was restored beside the `slot-claimed` result. |
| Local DR prose repeated stale workflow/history version numbers and created current-versus-target ambiguity. | Local epoch numbers were replaced with shared-register pointers; remaining v4 statements are explicitly current-source or historical, while the target cut remains accepted but inactive. |
| DR-BR-28 still listed future recents as typed cosmetic UI state, contradicting ledger-derived recents. | Recents were removed from the cosmetic-section list and are explicitly barred from UI state. |
| `HISTORY.md` and `TESTS.md` still required a future mixed-v3/v4 browser-history validator and referenced Core’s removed decoder-debt section. | Current history-v5 compatibility guards are now labelled temporary; checkpoint 3 replaces them with the exact reset target and no legacy browser decoder. |
| Retry and retention clauses allowed replacement of an unrun result, while DR-BR-03 permanently froze the committed selection that any retry needed to change. | Submission failure and terminal `disposition=unrun` now reopen selection at a new revision; the first `disposition=ran` is the authority-consumption boundary. |
| A fresh plan from a refused task had no safe way to reconstruct reviewed roots after drive-letter reuse. | `activate_task_pair` resolves both reviewed volume identities afresh and publishes two slots only when both accept; **Plan again** then starts a new task with the frozen setup. |
| Command arithmetic omitted retained bootstrap/cosmetic rows, BR-G-32 still froze the current nine-row table, and BR-G-46 had no explicit revision boundary. | BR-G-32's exact ordered test advances at every command-activating checkpoint; BR-G-46's map clause is additionally reopened at checkpoints 4 and 6, producing 12 then 18 unique commands and finally 32 target plus four retained rows, 36 total. |

### Pre-checkpoint 1 resolution

The follow-up adversarial pass rechecked the retained findings against their
owning DR-BRs, exact register rows, checkpoint dependencies, and BR-G gates. It
found no second closed retry loop or authority-consumption error. It did expose
two coupled scalar-contract defects—native file-identity narrowing and missing
typed outcomes for reachable timestamp/aggregate failures—which are resolved in
the accepted checkpoint-3 target. The recording/evidence axes retain one-way
settlement authority; task publication, compensation, leases, receipts, and
close keep one effect owner; location and Setup flows never promote display
text or cached probes; and projection windows remain detached from selection,
filesystem, and evidence authority. Four preparatory items are resolved:

- **Command arithmetic:** confirmed from the exact register rather than prose:
  checkpoint row counts are 6/8/8/1/6/3 for checkpoints 4/6/7/8/9/10, 32
  target rows total. The four retained bootstrap/cosmetic rows produce 12 after
  checkpoint 4, 18 after checkpoint 6, and 36 finally. BR-G-32's executable
  exact table advances with every activating checkpoint; BR-G-46 remains
  reopened only for the checkpoint-4 and checkpoint-6 revisions.
- **Scalar reachability:** `DEFENSE.md` §1.3 now distinguishes reachable native
  file-index/timestamp and aggregate-logical-byte cases from impossible single-
  volume capacity and post-admission counter overflow. Reachable boundaries
  use full-width opaque file identity, the path-local scanner warning, and the
  plan/domain logical-byte refusal; impossible cases are assertions, not
  ordinary user-facing failure states.
- **Checkpoint 3:** keep it before checkpoint 4 because the task/result
  foundation consumes v5 terminal, recording, and epoch shapes. Its three
  ordered commits now provide dormant consumer-preparation, producer/reset,
  and legacy-removal stops instead of one indivisible landing.
- **Bug ledger:** record only the newly distinct authorization, location-
  reactivation, file-identity-width, and cross-consumer protocol causal classes.
  Existing split-authority, publication-compensation, retention, and lifecycle
  entries already cover the other reusable classes and are not duplicated.
