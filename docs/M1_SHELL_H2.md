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
  Checkpoint 3 is the atomic core-event, terminal-summary, bridge-validator,
  ledger, history, CLI, and compatibility cutover.
- The exact `TerminalSummary`, refusal fact, recording fields, database epoch,
  scalar codec, checked-arithmetic policy, and reset posture are owned by the
  mapped bridge decisions and `DEFENSE.md` §1.3.
- Protocol targets are accepted but inactive until their implementation
  checkpoint; current-version documentation remains truthful until then.

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

### 3. Cut over atomically to event v5

Commit: `feat(protocol): cut over to exact core event v5`

- **Objective:** Publish the new truth contract across every producer and consumer and remove legacy machinery.
- **Acceptance:** Implement the mapped recording, reliable-event,
  terminal-summary, review-limit, scalar-codec, and persistence decisions from
  `M1_BRIDGE.md` and `DEFENSE.md` §1.3 across core producers, JavaScript,
  dispatcher views, history, CLI, and service. Preserve the checkpoint-2
  continuation boundary, keep bridge-only presentation omissions separate,
  perform the coordinated database epoch/reset cut, and delete all positive
  compatibility paths for superseded core-event versions.
- **Regression watch:** Whole-batch malformed-event rejection, cursor immutability, Gap recovery, Progress identity/monotonicity, terminal precedence, history audit degradation, Boolean-as-integer mistakes, unsafe-number leakage, and stale development databases.
- **Tests:** Core, executor, verifier, database, workflows, dispatcher, and interfaces departments; strict codec/payload round trips and wrong-version refusal; every detail/reason/review-limit population/axis variant, key, nullability, cardinality, and signed-64 bound; exact refused/unrun review-limit invariants, TerminalSummary copy, history all-null-or-exact group, terminal hash/repeated-finalization/reconstruction/CLI parity, and absence of presentation omissions from history; arbitrary-object/raw-int rejection; diagnostic omission without truncation and checked core-versus-presentation witness separation; exact maximum reliable envelope accepted plus one structurally over-limit rejection before sequence/queue mutation; maximum head drained alone under the bridge ceiling; duplicate-key and scalar corpora; startup/CLI reset guidance; required Node validator/reducer; ordinary suite; current-source v5 event/custody drift runs. Frozen old measurement artifacts remain untouched historical evidence.
- **Docs/review:** Mark v5 active in CORE, DATABASE, HISTORY, TESTS, M1_BRIDGE, INTERFACES, and README. Repeat the settlement oracle three times and independently inspect removal completeness.

### 4. Install task-centric lifecycle and compact artifacts

Commit: `feat(web): retain multi-session task artifacts`

- **Objective:** Remove the one-session assumption before adding production surfaces.
- **Acceptance:** Implement the mapped one-current-session task model,
  lifecycle and result authorities, owner claim, transactional observation
  attachment, task reads/control, exact-session release, task close, compact
  overlays/results, bounded terminal summaries, and page rehydration. Apply the
  exact publication and overlay invariants from `M1_BRIDGE.md`, and enforce the
  complete conservative pre-surface reservation floor from `DEFENSE.md` §1.3;
  checkpoint 11 calibrates and proves that already-active containment model.
- **Regression watch:** No task lock across facade, JSON, database, or filesystem work; non-atomic issue/retirement classification and lease acquisition; normal named publication advancing the task epoch; same-revision start/start, control/start, control/close, start/close, and release/successor races; claim-owner and attach/start compensation; terminal-event versus terminal-record race; stale drain/release; pinned-generation release or eviction; observer-thread and close-long-poll deadlock; receipts released before task close; references retaining full results; uncharged read/native/callback copies; capacity failure during release/close; mutation rows accidentally taking the lifecycle claim.
- **Tests:** Dispatcher/interfaces/service neighborhood; competing starts and
  unpublished-task claims; control/start/close/release interleavings; atomic
  lookup, issue, retirement, claim, lease, and epoch decisions; publication-
  versus-close barriers; exact overlay/result revision invariants; no mixing of
  plan, execution, inventory, integrity, or post-copy generations; every
  bridge/defense-owned population and retention refusal boundary; old/new
  diagnostic and artifact overlap; pinned-generation replacement/eviction;
  handler-saturation reconciliation; start/control/release/close replay and
  tombstones; byte-aware drain; reinjection; delayed terminal cleanup; and
  shutdown during observation.
- **Docs/review:** Update ARCHITECTURE, M1_BRIDGE, DESKTOP_UI, INTERFACES, and DISPATCHER. Review the complete ownership graph and initial BR-G-45 analytical model.

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
- **Acceptance:** Render typed/picker fields, probed recents/pairs, all implemented semantic controls, disabled ADS, raw bounded inputs admitted to backend-canonical complete snapshots, immediate path invalidation, admission freeze, truthful slotless partial-pair refusal, standalone inventory-task creation, and serial best-effort pair creation. No Setup edit writes global defaults and JavaScript owns no filter normalization.
- **Regression watch:** Default-settings race, hidden `null` fallback, filter amplification, stale slots, double click, command-ID reuse after edits, automatic retry with a new ID, partial pair activation, navigation/reinjection, and unsafe filesystem labels in the DOM.
- **Tests:** Exact Python/JS command policy mirrors and key validators; filter bounds/canonicalization; mixed batch successes/refusals; exact `slot-claimed` busy guidance; one-slot and atomic two-slot `slot_capacity_full` under all/partially pinned capacity with no native probing or partial slot; `recent_unavailable`; lost response both before and after task publication, with post-publication lookup using the bounded route rather than expired/consumed slots; document replacement; admitted-task recovery; settings fingerprint/commitment; headed typed/paste/picker/recent flows and hostile text.
- **Docs/review:** Update DESKTOP_UI, M1_BRIDGE, M1_SHELL, FEATURES, and INTERFACES. Close BR-G-47 only after headed evidence and parser review.

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
  the prior complete plan where the mapped replacement policy requires it.
- **Regression watch:** Rebuilding trees per window, operation-scaled responses, client-derived hierarchy/domain status, filter-dependent selection, synthetic ancestors, move annotations, stale selection/view revisions, double execution, and failed admission leaving selection frozen.
- **Tests:** Planner/workflow/interface neighborhood and the exact BR-G plan
  fixtures/boundaries in `M1_BRIDGE.md`; first-excess/no-partial publication;
  review-header rehydration and revision guards; capacity fact availability;
  reviewed-versus-fresh preflight behavior; typed notice merge, omission, and
  action exclusion; same-target grouping and exactly-once operation projection;
  folder/group selection and rollups; stale/replayed mutations; execution-
  refusal retry; search/filter/facet/window/dependency boundaries; move-peer
  positive and suppression cases; off-window follow; destructive confirmation;
  hostile DOM; latency/memory; and headed production witnesses.
- **Docs/review:** Update PLANNER, WORKFLOWS, M1_BRIDGE, M1_SHELL, and DESKTOP_UI. Close BR-G-35, BR-G-37, plan BR-G-32, and the plan portion of BR-G-42 after adversarial selection review.

### 8. Deliver execution review and ledger-current evidence

Commit: `feat(web): add execution review and ledger evidence`

- **Objective:** Complete live execution, retained review, and trustworthy full-hash display.
- **Acceptance:** Attach execution atomically; render v5 progress, pause/resume/cancel, indexed follow, terminal axes, item/task recording issues, and retained file-list windows whose plan rows carry an exact `ExecutionOverlay` while leaving the separate post-copy overlay untouched. Add one batched transactional operation/run/inventory evidence query and bounded per-item detail including the item omission witness.
- **Regression watch:** Live-versus-terminal overlay disagreement, Gap loss, later task failure suppressing earlier evidence, unrecorded item borrowing another inventory hash, N+1 queries, canonical target collisions, latest-writer confusion, diagnostic amplification, and premature session release.
- **Tests:** Executor/database/workflow/interface neighborhood; all filesystem/
  recording combinations; exact overlay invariants; separate omission axes;
  committed item followed by later task/audit failure; scope match/change/
  invalidation/missing; full digest and no plan hash; Gap-plus-terminal
  reconciliation; navigate away/back; the bridge-owned maximum result overlay;
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

Commit: `feat(web): close task lifecycle and retention budgets`

- **Objective:** Prove cleanup, shutdown, and retained-task containment across the completed surfaces.
- **Acceptance:** Calibrate and verify without post-selecting or silently
  changing the checkpoint-4-frozen analytical constants; prove the aggregate
  task guarantee and count wall owned by `DEFENSE.md` §1.3, plus
  reservation/shrink/refusal, live closing, terminal presentation/release
  retry, explicit close, repeated create/release/close, complete response/native/
  browser transients, and concurrent shutdown. Any policy defect lands
  separately, revises the enforced constant before a new run, and resets the
  evidence run.
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
