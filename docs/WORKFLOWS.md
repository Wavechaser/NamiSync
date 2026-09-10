# Workflows Module

Status (2026-08-27): M0 reviewed sync/history plus M1 Stages 1-5.5 are
implemented. The local
composition root now owns role-free inventory and standalone
baseline/verify/rebaseline, their production dispatcher registrations,
typed execute/verify checkpoints, optional post-execution
verification, compound history/views, generic history reads, semantic-settings
snapshot/patch translation, and the shared facade used by the location CLI
commands. Stage 5.5's workflow-owned selection semantics are now implemented:
direct user deselection remains distinct from safety exclusion, execution
re-derives the authoritative set, and the workflow-owned typed checkpoints
preserve that provenance and executor continuation truth.
Stage 5.5 facade integration is complete and the planning-source ownership wall is
active. Shared location-candidate admission and bounded run-derived remembered
locations are also implemented; their current behavior is owned by INVENTORY
and DATABASE, with application entry points in INTERFACES. Setup widgets remain
pending. Stage 6 desktop behavior is finalized in `BRIDGE.md`; queue durability,
maintenance/retention, replay, undo/repair, and ingest remain later work.

## Stage 6 Second-Half Workflow Contract

Exact internal event/results are source-owned under `namisync/core/`; [BRIDGE.md](BRIDGE.md) owns their external encoding, and
numeric/retention walls in [DEFENSE.md](DEFENSE.md) §1.3. Workflows consume
those contracts without receiving an interface-owned task claim.

Execution continuation is opaque process-local custody. The frozen
`ExecutionCheckpoint` reuses an `ExecutionSetAuthority` snapshot for shared
execution truth: status, sparse recording reasons, ordered task issues,
aggregate byte high-water, and transient publication evidence. It adds only the
phase-specific remainder: verification choice and exclusion cursor for execute,
or candidate selection and compound phase/result axes for verify. Construction
validates the admitted domain request and detaches mutable state; reopening
materializes fresh mutable overlays. There is no checkpoint schema version,
JSON form, checkpoint-specific authority/adoption wrapper, or
`adopt_checkpoint()` path. Transient evidence never becomes history, ledger,
desktop artifact, or JavaScript state. Dispatcher terminal settlement clears
the current live record's opaque checkpoint, and its separate metadata-store
projection never persists it.
This is not whole-process reference erasure; the scope and M2 protected
recovery requirement are defined in [DISPATCHER.md](DISPATCHER.md#session-store).
Manual exact post-copy verification remains unrealized; its accepted contract
classifies current durable evidence in the original execution scope.

Installed NamiSync modules are trusted-but-fallible internal (rung 3)
participants, not adversarial security principals. Their public returns are the
workflow's named ownership-transfer points: admit a compound result once, then
share immutable base values with first-party read-only consumers. These
adoption paths no longer deep-reconstruct immutable scan, plan, observation,
verdict, or execution authority graphs. Mutable execution overlays still
receive one compound audit at each producer return and shallow prior-truth
guards at reentrant (rung 2) callback seams. Where lifecycle permits, edge
reconciliation is incremental and whole-authority checks occur once or a fixed
number of times per transfer or phase. Shallow or fixed-frequency describes
graph depth and invocation placement, not constant cost: a guard may still copy
or walk retained settlement/completion prefixes or candidate tuples. External
(rung 1) inputs are validated and bounded at ingress, while applicable
populations remain independently bounded at every applicable rung. Fresh
filesystem observation, callback ordering, and exception-graph retirement
remain separate requirements.

Checkpoint populations remain subject to their existing domain limits at the
constructors that own them. Internal custody does not repeat those checks or
translate the graph into a parallel primitive vocabulary. External interface
adapters retain complete-request bounds at ingress, while the dispatcher treats
an admitted checkpoint as an opaque domain object.

Workflow aggregation preserves operation-local recording truth and the
first observation of each task issue in order: later failure cannot rewrite an
emitted item or revoke committed evidence. Exact event v5 now carries the item
recording and omission fields, while its item-free terminal summary carries
task issues and aggregate witnesses. Presentation-only omissions remain outside
the core result and history contracts.

`workflows/views.py` reuses `envelope_to_dict`'s one canonical event-body mapping
and changes only the live wrapper key from persisted `seq` to browser
`sequence`. It does not reconstruct or certify a trusted body. Exact validators
remain for public session-record and operation-result views at their consuming
boundaries. Existing frozen body mappings remain supported, and generic
result-free session snapshots remain legal without implying terminal delivery.

Workflow accumulation follows the active exact checked-arithmetic contract in
[BRIDGE.md](BRIDGE.md) and
[DEFENSE.md](DEFENSE.md) §1.3 without a workflow-local numeric variant.

## Purpose

Workflows are plain top-to-bottom functions and the only place operation modules
meet. They translate a typed request into sequential calls, pass immutable
outputs forward, aggregate filesystem/recording/history-aware results, and
declare required resources to dispatcher. They do not implement scan/diff/copy/
hash/SQL/UI behavior and never coordinate through signals or callbacks-for-
control.

Every runtime dependency arrives through one composition-root `deps` object:
clock, scanner/change source, repositories, planner/policies,
observer/preflight, executor, verifier, recorder, and later importer. Planning
adapters may snapshot semantic defaults when constructing a request; admitted
execution does not receive or reread a settings provider.

The local runtime owns two lazy presentation readers: one ledger repository for
inventory/mapping reads and one history repository for summary/page reads. Each
role lock covers admission, query, and materialization; successful requests leave
no open read transaction. Shutdown quiesces admission before waiting for active
readers and keeps failed closes retryable without reopening partly closed owners.
Query failures retire the affected reader; replacement handles always undergo
full admission. Planning correspondence, worker-local integrity/location readers,
recorders, and database-pair admission keep their separate lifetimes. `DATABASE.md`
owns the detailed lifecycle, reset, and diagnostic cost contract.

The same runtime owns execution and inventory detail maps for terminal
interface readback. Their explicit idempotent drop operations remove exactly one
run or request. Runtime close clears both maps only after the history store and
both presentation readers have closed successfully; any dependency-close failure
leaves the maps intact for the serialized retry. The service owns the separate
session-to-detail relation and invokes a single drop only after dispatcher
retirement, so workflow code does not infer a detail lifetime from terminal
state alone.

### Node tree substrate

`build_node_tree` is a pure workflow helper over path-keyed members. It emits
deterministic preorder structure, immutable id/path indexes, direct member ids,
subtree membership, and bottom-up member counts. The empty-key root is always
addressable and the canonical path index remains one-to-one and domain-only.
The builder checks source occurrence `N+1` against its local wall before
accessing that member. Within the wall it reconstructs and validates each exact
member before duplicate classification, and it never retains the first excess
source member. It keeps one minimum display spelling for each canonical path key.
This source-row bound does not measure synthetic ancestor/index construction
or sorting cost; PRESENTATION owns focused scale verification for those behaviors.

Plan projection preserves that single path authority when several immutable
operations share one target. It retains one path/group row and emits every
operation once as a direct member, with a separate operation-id index for item
anchors. Group presentation never changes executable membership or grants
filesystem-folder action semantics.

Informational warning/notice leaves are interleaved only after the domain tree
is built. They have typed stable identities and deterministic attachment, but
never enter the canonical path index, subtree membership, selection, rollups,
or actionable scope. Implemented node codecs remain source-owned. Ordering, projection behavior, diagnostic
omission, and population walls are owned by [PRESENTATION.md](PRESENTATION.md) and DEFENSE.
Presentation filters, move grouping, overlays, and caches remain Stage 6
service/interface concerns rather than tree-builder policy.

### Review publication

Stage 6 injects an immutable workflow-owned `ReviewPublicationContext` and a
workflow-level `ReviewPublicationSink` implemented by the task service. The
incremental collector either stages one complete immutable plan/inventory
candidate—including indexes, rollups, charge, and omission identities—or
returns the typed no-partial population refusal. It never returns an unbounded
or partial raw graph.

The workflow invokes the sink only for the exact session/slot/tree intent it was
given and stages at most once. Once successful fresh preflight has staged its
complete notice generation, expected execution failures and cancellation are
contained into a normal terminal `OperationResult` so the stage survives for
reconciliation. Missing, duplicate, rejected, contradictory, or escaped
post-stage behavior is structural producer failure, not a recoverable workflow
result. The exact stage/result matrix, latch behavior, owner reconciliation,
fault disposition, and retry boundary are bridge authority.

An initial plan or inventory publication has no prior baseline. Inventory
refresh evaluates the complete candidate in place of the old inventory for
population admission but does not reclaim the still-owned generation before
atomic swap. Fresh execution preflight similarly replaces its complete notice
set—even when empty—without replacing the immutable plan. Workflow never
reprojects a staged candidate after publication.

## Reviewed Sync

### Plan session

The plan session owns one cumulative `PlanReviewAdmission` ledger. Scanner,
planner, observer, preflight, and result-adoption gates receive exact counter-free
`PlanReviewProducerAdmission` capability that exposes no retained-budget
`admit` capability or counters. The ledger and producer capability share only
one opaque same-run admission token so workflow can distinguish a legitimately
issued capacity signal from a tokenless or different-run same-domain internal
failure. Correspondence keeps its ordinary two-argument protocol; its concrete
database query is structurally bounded by admitted scan keys and identities,
then workflow
captures the fallible result under the same counter-free producer gate. Each
raw population has an independent first-excess gate. `ScanResult` construction
owns complete graph validation; workflow adoption retains exact result/tuple
transfer and requested root/scope checks before sharing the same result by
identity with first-party read-only consumers. Workflow still
copies the fallible mapping result, but it exact-adopts the planner's immutable
`Plan` once after compound validation and shares that same plan identity with
review, artifact, and later first-party consumers. Observer and preflight
results are likewise exact-adopted once after compound validation: judgment
receives the observer's world identity, and the artifact retains the preflight
callback's verdict identity. Unsupported reflective mutation of these slotted
contracts is not treated as a supported collaborator result.

Only unavoidable shallow slots that coexist in the final scans, plan,
observed world, and verdict commit to the retained ledger, together with the
final operation and informational rows. Construction builders, sorting and
indexes, selection/exclusion derivation, and other sequential temporaries are
not retained owners. Each preflight cycle now creates one frozen
`ExecutionReview`: plan review gives it empty status, while execution/resume
copies status only after capturing mutable execution authority. The same review
reaches observer and preflight; the observer result is admitted once and that
same deeply read-only world reaches preflight and the retained verdict. The
verdict must point to that exact world; an equal replacement is an ordinary
contract failure, not a review-capacity refusal. There are no disposable plan
previews, second callback-world copies, or verdict reconstruction. The workflow
maps the first exact private plan-limit signal to `REFUSED+UNRUN` without saving
a plan or exposing a partial result.

Plan and inventory use distinct private exact signal types and separate
same-run admission tokens. Workflow accepts only an exact, correctly scoped
signal carrying the active domain token, reconstructs a fresh exact fact, and
retires the raw signal graph before returning. A tokenless or different-run
same-domain signal from a trusted-but-fallible module fails loudly rather than
becoming `REFUSED+UNRUN`; a current-run signal with the wrong fact scope is
invalid, and ordinary lookalike or cross-domain exceptions retain their
ordinary failure identity. Reflective extraction or mutation of private tokens
remains outside the supported fault model. Plan-save and inventory-details
callbacks run outside signal translation, so an exact private signal raised
there retains ordinary failure identity. Preflight output validation requires
an exact identity relation to the already admitted deeply read-only world, so
replacement cannot become capacity refusal. Scanner, planner, and selection
behavior is unchanged; observer and preflight receive the immutable review
projection instead of mutable continuation.

These planning-source row and shallow-reference counters are admission facts,
not heap estimates or complete-runtime memory claims. Construction, presentation,
serialization, native/browser copies, and multi-session ownership remain outside
this workflow admission.

`run_plan` now isolates its phase frame and retires traceback/cause/context
before any ordinary or process-fatal error escapes. Root/path adapters project
their existing logical, redacted message and raise a fresh unchained
`ValueError`. An unadmitted signal becomes a fresh unchained provenance
`RuntimeError`, and a malformed or wrong-scope signal becomes a distinct fresh
unchained validation `RuntimeError`; both raw signal graphs are retired first.
Phase delivery, scanner, correspondence, planner, observer, preflight,
ordinary lookalike failures, and save failures otherwise preserve their
existing public type and identity without retaining request/root/options/scan/
plan/world/verdict locals. This closes raw exception ownership, not path-message
construction or the other unmodeled construction/callback costs.

1. Lexically normalize and validate distinct non-nested roots and request
   semantics without following filesystem links. The shared core chain-only
   admission obtains the current native anchor and uses extended spelling only
   for no-follow probes of every configured-root component below it,
   returns ordinary lexical `Path` values, compares separately resolved
   physical roots for overlap, refuses reparse, device, or ordinary-ambiguous
   root names, and never persists or displays a `\\?\` prefix.
2. Resolve volume/location/mapping evidence without persisting preview-only
   configuration.
3. Scan both roots through the single structural `population_admission`
   parameter and independent raw source-population gates; validate and adopt
   each exact immutable scan once under a separate producer gate, then share
   those identities with correspondence, planner, and the retained plan
   artifact.
4. Read immutable prior correspondence through a ledger query whose keys and
   identities come only from the already admitted scans. Runtime query indexes
   and result construction are therefore structurally bounded rather than
   separately metered; workflow captures the trusted-but-fallible internal
   (rung 3) correspondence result exactly once before giving it to the planner.
   Then it reads one complete semantic-settings snapshot. If the request
   supplies a deletion-policy override, replace only that field in the snapshot.
5. Apply filters/policies and plan.
6. Derive the ordinary deterministic safe selection: retain additive/no-op work, mark
   direct blockers `BLOCKED`, quarantine overlapping/dependent work as
   `DEFERRED`, and withhold destructive/identity moves when either scan is
   incomplete.
7. Observe/preflight that exact selection for review information.
8. Return the immutable plan/verdict with reviewed authority and typed warning/
   refusal facts intact after all disposable collaborator copies retire;
   terminate and release locks. Stage 6 projects those facts as inert notices
   rather than flattening or dropping them.

### Execution session

1. Re-derive the authoritative execution selection from the immutable plan,
   safety exclusions, and canonical `user_deselected` set. Validate the exact
   core `Commitment` defined in [execution.py](../namisync/core/execution.py); execution cannot
   resupply a frozen Setup choice. Refuse a malformed or mismatched commitment
   before preflight. An all-skipped result refuses because there is nothing to
   execute; a selected `NOOP` remains executable work.
2. Reacquire required physical-volume custody.
3. Consume the immutable semantic snapshot bound into the reviewed plan; never
   reread global defaults to decide admitted filesystem behavior.
4. Freshly observe/preflight filesystem and volume state under execution
   custody; refusal mutates nothing.
5. After a successful verdict, remove exact prior-run temps once from the
   observed touched-target-parent scope; cleanup failure stops before executor
   admission, so capacity credited by preflight cannot become unsafe.
6. Execute selected dependency-closed work through the pipelined XXH3-aware
   backend, record each settled operation through the run recorder, and return
   ordered `operation`/`execute` items with independent filesystem, recording,
   and audit truth.

7. When explicitly requested, translate every successful byte-producing
   publish into a transient post-copy candidate, verify it under the same
   custody/run token and reviewed target-volume authority, and retain rowless
   candidates when copy recording failed.
8. Return one ordered operation+integrity item stream and independent execute/
   verify phase summaries. Finish the one logical ledger run exactly once; a
   pause leaves it unfinished for same-process resume. A malformed resumed
   continuation is refused before domain work and finishes the already-open
   run directly by its custody-bound token; it never attempts to re-begin that
   run from the malformed carried selection.

The default execution path still ends after step 6, preserving M0 behavior.

Human review occurs between sessions with nothing running. Commitment is the
durable preauthorization and has no time expiry, but binds exactly one plan,
dependency-closed selection, approval, and frozen linked-verification choice.
Scripts and queue releases may replay it; no API plans and executes in one
unreviewed breath or supplies a later linked-verification choice.

The implemented Stage 5.5 selection substrate keeps safety exclusions and
direct user deselection distinct. Effective exclusion closes downward over
dependencies; reselection removes the requested operation and its transitive
dependencies from `user_deselected`, but can never clear a safety exclusion.
Execution rejects an empty or mismatched re-derived set before observation and
preflight. The service integration owns review revisions, lower-level direct-
artifact replacement discard, and the reviewing/committing/committed
transition; the client submits revisions and opaque ids but never becomes
selection authority. The accepted M1 desktop never replaces a published task
plan in place. Failed execution admission restores reviewing; a preflight
refusal after admission leaves selection committed. Terminal subset retry and
selection reopening are deferred, not implicit workflow recovery. Explicit
Plan again resolves the retained reviewed location identities into fresh Setup,
then creates a new task with fresh scans and default selection, requiring new
review rather than replacing the old artifact or carrying authorization.

### M0 implementation

`workflows/sync.py` contains the plain planning and execution functions.
`LocalWorkflowRuntime` is the local composition root: it injects every module,
derives immutable prior-correspondence query bounds from the current source and
target file scans, resolves that subset through a one-snapshot read-only
repository query, declares physical-volume resource keys, owns detached typed
process-local checkpoints, starts ledger recording only after commitment and
fresh preflight, and supplies the dispatcher history observer. Planning and declined review do
not create either database. Invalid database locations are rejected before the
plan session, and an execution refusal may still create independent audit
history while leaving managed files and ledger configuration untouched.
Execution start custody is established only when the invocation actually enters
workflow work, or when a pre-run pause snapshots a resumable start. Terminal
refusal or failure before ledger recording releases that custody; a cooperative
pause retains it for exact resume/cancel settlement.
Execution recomputes the checkpoint's plan fingerprint before comparing
commitment, so resumed execution cannot hide a changed plan behind retained
custody. `ExecutionCheckpoint` construction preserves every fingerprint input,
including `SyncOptions.propagate_source_casing`, and snapshots the mutable
execution overlays. Its `materialize()` operation creates fresh overlays for
each open. The complete semantic snapshot remains available through primitive
service read/partial-commit views, but no settings CLI command is added.
Whatever interface commits the source-casing choice, review and commitment bind
it rather than letting execution reinterpret filename spelling.
The interface-facing `PlanOperationView` retains `prior_target_path` separately
from source and planned target paths. Review adapters use it as the displayed
origin for recase, move, and move-update rows, so the target-side rename is not
lost while translating the immutable core plan into a presentation model.
Domain text retains the existing valid-Unicode and bounded-value rules at the
constructors that own it. Ledger hashes, history persistence, and interface
messages keep their own boundary serialization; process-local checkpoints do
not share or emulate those wire contracts.

M0 automatically selects the maximal safe dependency-closed subset. Directly
blocked items remain in the reviewed plan as `BLOCKED`; operations touching
their source/target correspondence region or depending on an exclusion become
`DEFERRED`. If either scan is incomplete, `move`, `move_update`, `trash`, and
`delete` are withheld globally because absence and identity correspondence are
not proven, while `copy`, `update`, `mkdir`, and guarded `noop` remain eligible.
The commitment digest binds this derived selection and fresh preflight enforces
the same safety envelope if another caller supplies a different selection.

Workflow emits excluded items after execution settles and merges them into the
terminal result without rewriting successful filesystem status. Blocked intent
never writes the main ledger; selected no-ops still execute their live guard and
refresh source/target correspondence. Direct user deselections emit `SKIPPED`
with reason `user-deselected`; dependency fallout stays `DEFERRED`, so retained
history can reconstruct the same classification without guessing. Durable plan
files, queue release, linked verification, and integrity workflows were not
part of the implemented M0 slice. Stage 3 now implements the standalone
inventory/integrity half without changing that M0 execution boundary; Stage 5.5
now supplies the workflow semantics for process-local user selection editing,
with service exposure completed by the facade integration.

Stage 4 linked verification deliberately does not build its immediate candidate set
from inventory rows. The execution continuation retains each successfully
published operation's post-publish attestation plus its complete recorded
identity, or no identity only when the same operation carries
`record-write-failed`, then turns those values into transient verifier
candidates. This survives an in-process pause because evidence, recording
attribution, task issues, and aggregate byte high-water are retained in the
typed checkpoint beside execution status;
neither the continuation nor process-local plans survive closing/restarting
the M1 application. Later standalone integrity sessions use durable ledger
evidence.

Before linked execution can publish a verify continuation, the workflow applies
the core 1,024-byte whole-value diagnostic policy to the executor result's phase
and failure inputs. Each newly omitted input advances the retained
`ExecutionSet.omitted_detail_count` once. The executor result's incoming count
must already equal that execution-set authority; a contradiction fails before
checkpoint publication instead of being lost during final reattachment. The
execute-phase error is then formed from the bounded failure type and message
and checked again as one whole value. Individually bounded components do not
exempt an oversized combined value. An invalid or oversized combination is
omitted with one additional witness. `VerifyContinuation` reconstructs every
execute-phase field into a fresh exact `PhaseResult`, so subclasses, forged
counters, invalid text, and caller aliases cannot enter custody. Checkpoint
construction performs that detachment, and both public execution entry points
admit the typed request before workflow or canceled-settlement use. Reflective
post-admission corruption is therefore refused rather than retained in a direct
result. Once candidates
exist, the normalized executor result is released before the continuation sink;
only its bounded phase projection and the already-selected item tuple remain in
the workflow frame. The count therefore survives sink failure, pause, resume,
cancellation, and terminal projection without being added again.

The implemented compound transition rules are explicit:

```text
execute
  pause  -> snapshot status + item/task recording truth + evidence + byte high-water
  cancel -> typed terminal canceled; preserve recording truth; start no readback
  settle -> when requested, enter verify for candidates or missing-evidence failures

verify
  pause     -> snapshot candidates + completed ids/bytes
  cancel    -> retain filesystem truth; integrity is canceled/incomplete
  mismatch  -> retain filesystem truth; report integrity finding
  exception -> retain filesystem truth; incomplete verify PhaseResult
  complete  -> settle one compound terminal result
```

The five verification terminal branches share one workflow-owned pure projection
of the continuation's settled execute status, phase, and byte pair. Each path
supplies its already-decided verify phase, accepted items, recording,
cancellation, and diagnostic; the projection performs no policy or collaborator
work. Existing generic cancellation settlement remains separate.

Running execute cancellation returns the same typed workflow result whether or
not post-copy verification was requested. It finishes the one ledger run with
the `ExecutionSet`'s current recording axis, so an executor-detected degraded
recording cannot be replaced by the generic runner's default `OK`. It captures
the executor's emitted outcomes, emits plan exclusions, and merges the complete
item result in reviewed plan order. The execute phase summary remains
compound-only; a plain execute cancellation does not invent a
verification-shaped phase.

An escaping ordinary execute exception follows the same authority rule. The
workflow constructs its failed result from the `ExecutionSet`'s settled-item
state, fixed reviewed byte budget, and aggregate byte high-water rather than
asking the generic runner to reinterpret the latest lossy Progress snapshot.
Within the opened execute recording, exclusion delivery retains only the prefix
accepted by the reliable sink. Its first ordinary rejection is terminal for
that delivery attempt: neither accepted siblings nor the rejected item are
re-offered by failure projection. Successful execution, cancellation, and an
already-failing execute path all use the same failed-result projection if
exclusion delivery fails. That result preserves accepted items, continuation
byte counters, and the first sink error (with guarded optional rendering);
ordinary sink failure takes precedence over cancellation. A secondary recording
close failure is then attached before the generic runner publishes terminal
and dispatcher clears its live continuation reference. This needs no
domain-specific generic runner hook or change to dispatcher custody.
After each accepted exclusion, the execute checkpoint advances its
`reported_exclusion_count` before invoking the hostile continuation sink, then
publishes that custody before another sibling is offered. Sink cancellation
therefore continues from the next suffix item rather than replaying the accepted
one. Resume re-derives the same plan-ordered exclusions, skips the retained
prefix, and reconstructs the direct result in reviewed plan order. A terminal
refusal, failure, or cancellation cannot be interrupted into a resumable state;
cooperative control at that point becomes the terminal emission failure. Event
publication and continuation capture remain separate process-live actions, so a
process crash between them is not an exactly-once guarantee and belongs to the
future protected recovery design.
Fresh commitment or preflight failure/cancellation does the same before the
executor or run recording opens, retaining `UNRUN` disposition and the
phase-free result shape while still reporting the reviewed byte budget. Control
during a fresh refusal's exclusion suffix is contained in that same typed
`REFUSED+UNRUN` result with only its normally accepted item prefix.
Plain execution retains its phase-free result shape; linked execution adds the
execute phase summary. Failure to enter the run-recording context likewise
returns continuation-derived counters with degraded recording, while a context
exit failure is secondary to an already-computed filesystem/result truth and
degrades recording without replacing that truth. Cooperative control and
`BaseException` causes still escape; a secondary context-exit failure is noted
without replacing them. If that happens while pausing, the active execute or
verify continuation is first degraded and recaptured, so paused cancellation
or resume cannot recover an `OK` aggregate from the failed recording owner.
Exit-failure capture is unconditional, including an execute continuation whose
aggregate already reflects the newly recorded issue. With verification present,
close failure still belongs to the execution set's task issues as well as the
combined recording result; it does not rewrite settled filesystem status.
Recording-open, finish, and close attribution establishes a typed task cause
before optional logical diagnostics. If rendering raises an ordinary exception,
the issue retains `detail=None`; it cannot turn a recording failure into clean
recording or replace an existing filesystem error. Required result messages and
secondary exception notes use a fixed diagnostic-unavailable message while
retaining the original error type. This containment also covers cancellation
finalization, existing-run finishing, and secondary emission/capture diagnostics on
an already-failing recording path. Successful details keep the existing
first-observation, complete-bound, and omission-count rules.
During linked verification, the phase summary counts
successfully emitted reliable outcome identities as a floor, so a later
continuation-bookkeeping failure cannot erase an already-published settlement.
Executor advances operation status, recording reason, and transient evidence
only after reliable item emission returns; a sink failure therefore leaves no
continuation-only settlement. Candidate completion follows the same ordering.
Workflow retains the canonical item immediately after that normal emission
return, before any later reconciliation can fail. Executor and verifier
aggregate returns may confirm their own terminal axes but cannot contribute
workflow-owned phases or replace the accepted stream.
Execution checkpoints reconcile settlement both before and after invoking the
caller-owned checkpoint, so an unreported mutation cannot cross a reentrant
boundary and a returning callback cannot leave new drift unchecked.
Linked verification likewise reconciles only the current accepted-outcome and
completion delta at item, progress, and checkpoint seams. An accepted outcome
may remain pending while its first-party verifier returns from the reliable
emit and marks completion; a second outcome cannot cross that gap. The complete
mutable execution overlay is audited once after the executor returns, together
with emitted-settlement reconciliation. A linked verifier return gets one
strict no-execution-change audit plus its existing post-copy completion audit,
instead of rescanning immutable plan/fact graphs around every emitted item.
Executor outcomes bind through one workflow-local map of the canonical
`PlanOperation` references; final plan-order iteration uses the operation being
traversed rather than a duplicate fact graph.
Normal, control, and ordinary-error returns share those same once-only audit
owners. Public execution and direct canceled-settlement entry each perform one
complete continuation admission; nested cancellation reuses the admission
already held by the running workflow.
Standalone integrity uses the same pre/post checkpoint rule and incremental
accepted-outcome/completion handshake. It retains a reliable outcome as soon as
the caller-owned sink returns, before checking whether that callback changed
selection custody, and permits pause or cancellation to escape only from a
settled edge. Its complete selection receives one runner-return audit, plus one
post-transfer audit only when a selection sink is configured. First-party
progress is adopted before an external edge; callback return must preserve the
exact adopted counters rather than manufacture monotonic progress.
Each external edge still requires the same admitted selection container,
candidate tuple, and immutable execution identities, so ordinary callback
replacement cannot redirect later verifier work; frozen candidate-leaf
reflection remains outside the supported fault model.
Immediately before each recording-open callback, the workflow projects the
already-admitted execution set to one frozen
`RecordingSpec(plan, selection, run_id, commitment)`. The open callback receives
that spec; the production `_LedgerRunRecording` retains the same object through
`finish` and context exit. An existing-run finish callback captures its required
finisher once, then constructs that same spec inside its execution-authority
guard after snapshotting and before revalidation. Recording callbacks and the
local recorder runtime therefore receive no mutable execution status, evidence,
progress, or recording-attribution container. Workflow helpers keep the
execution set only to attribute callback failures and derive aggregate
recording truth. Shallow fixed-reference and prior-overlay guards remain around
recording open/enter, finish, context exit, existing-run finishing, cancellation,
checkpoint/exclusion sinks, and verify-degradation publication. They retain
the first safe pre-callback issue/counter baseline and preserve the accepted
item prefix across ordinary failure, paused cancellation, existing-run finishing,
and context exit. Settlement order, callback count, checkpoint state, and recorder
outcomes are unchanged.

Fresh preflight still runs on every resume. If an already-started execute
continuation is refused or faults there, workflow finishes the existing run
through the required finisher as `FAILED+RAN`, with settled execute counters
preserved; it never claims a fresh `REFUSED+UNRUN`. If the recording boundary
cannot open while finalizing an already-failed execute or verify continuation,
that open failure is attributed without replacing the existing failure result.
Canceled open failure likewise passes the newly degraded axis to existing-run
finishing before taking its returned aggregate. A verify-resume preflight refusal preserves the
settled execute filesystem status and adds a zero-work incomplete verify phase.
Selection derivation, commitment diagnostics, commitment refusal, preflight
exceptions, and preflight refusal all route through one pre-run settlement
dispatcher. That owner selects fresh, resumed-execute, or verify-continuation
policy while keeping fresh commitment refusal item-free and fresh preflight
refusal responsible for its accepted exclusion suffix. Cancellation remains a
separate control dispatch.
All terminal paths after recorder entry share one finish-once boundary.
`PauseRequested`, `KeyboardInterrupt`, `SystemExit`, and other
`BaseException` subclasses are not normalized into a workflow failure.
`PauseRequested` or `Canceled` raised by the recording factory or its entry
boundary likewise remains a control transition: pause escapes for custody
snapshotting, while cancellation projects authoritative continuation counters
without reopening the recording factory or consulting lossy Progress.
A consumed callback failure is converted through the core
`retired_failure_detail()` owner to its logical-path `FailureDetail`, then its
traceback/cause/context is retired before another callback runs. The same owner
is used for integrity and dispatcher terminal failures; integrity candidate
limits supply their already-classified fact type as the explicit type-name
override. Exclusion delivery retains only the closed first-failure value rather
than the raw exception. Recording contexts
evaluate a collaborator's exit truth exactly once; every truthy value suppresses
and retires the body exception, while a truth-test failure follows normal Python
propagation. Secondary diagnostic rendering and note attachment catch their own
hostile `BaseException` and cannot replace the primary. An escaping primary
keeps its identity and caller-owned custom state without keeping the execution
phase frame.
A resumed execution canceled at the dispatcher's entry checkpoint is settled
from its retained semantic checkpoint before `invocation.run()`, so the same finish-once
ledger boundary runs. Once that exact cancellation settlement is elected, its
validated process-local start claim is released in `finally` even if recorder
open throws or finalization degrades.

## Integrity Workflow

Inventory, baseline, verify, and rebaseline are location-centric,
not plan- or mapping-dependent. The workflow resolves or registers one selected
location, re-resolves its volume identity at start/resume, performs full or
selected refresh, commits inventory, constructs canonical selection, runs the
integrity module with the required XXH3-128 factory, flushes recorder, and
returns inventory plus nominal phase-tagged outcomes. Missing inventory is
created automatically; the user is not told to run a hidden prerequisite
manually.

Resolution carries the current sole selected mount even when a stable volume
has moved from its stored hint. The scan and every subsequent verifier open are
bound by an ephemeral `RootAuthority` built from the fresh resolution's logical
root, selected mount, and the location's full stable `VolumeId`, so a remount
between refresh and hashing cannot be recorded under the old location
authority. Post-copy verification instead derives the same contract from the
committed plan target root, its optional reviewed device anchor, and target
volume identity; neither workflow persists the authority in a continuation.
Before the scan, inventory uses that resolver-selected mount in core's
chain-only admission and then performs its existing accessibility probe; it
does not add a second volume observation or move ambiguity policy into core.

Scope has three semantic shapes: `FULL`, exact `PATHS`, and recursive
`SUBTREES`; mixed requests canonicalize overlapping roots and selecting the
location root becomes `FULL`. Exact refresh reconciles only named rows.
Completed subtree refresh reconciles every indexed descendant using a literal
canonical-path range, while full refresh reconciles the whole location. These
are separate recorder branches, not a two-valued full/selected shortcut.

Folder verification resolves an opaque location-scoped node id to a canonical
path and freezes all eligible indexed descendants independently of the current
filter/window. An unreadable frozen subject emits a visible `unsupported`
integrity result, makes verification incomplete, and does not suppress eligible
siblings. Non-subject-specific incompleteness still refuses before hashing. UI
receives refreshed inventory and typed scan warnings at the scan-to-hash
handoff so it never shows stale/empty or falsely complete state during work.

Baseline, verify, and rebaseline register pause support. Their continuation
retains the exact admitted candidate ids plus completed ids/bytes; resume
freshly inventories and guards those remaining rows without adding a newly
appeared row. Inventory and plan register pause unsupported and remain
cooperatively cancelable. The production interface registry contains all six
current workflow kinds, and the CLI reaches each through the shared service.

After integrity selection, running cancellation or ordinary failure derives
terminal item and byte counters from that live checkpoint rather than the
latest lossy Progress snapshot. Canceling a paused baseline, verify, or
rebaseline session settles the latest typed checkpoint without reopening the
workflow. It carries `processed_bytes`, the nondecreasing physical-read
`bytes_total_high_water`, and one-way aggregate `recording`; a resumed
invocation or paused cancellation cannot regress those axes. The byte pair
measures attempted physical work rather than durable
publication, while accumulated reliable outcomes and recorded evidence remain
the independent settlement and durability authority. The same request-level
`FAILED+RAN` projection applies if resumed volume resolution is offline or
ambiguous, its refresh is incomplete, or recorder setup fails before
`IntegritySelection` can be reconstructed. Fresh resolution refusal remains
`REFUSED+UNRUN`; a fresh incomplete refresh remains `FAILED+RAN` with zero work
counters.

Frozen resume selection does not materialize the location's complete inventory:
the workflow extracts canonical location-owned row IDs and asks the repository
for 400-ID chunks under one read snapshot, then restores the original admitted
order. Malformed, foreign-location, or missing saved IDs refuse resume instead
of broadening it. A stale-before run consumes the repository's stale query
directly and fetches only exact already-completed rows needed for settlement.
Explicit selected-path and intentional full Verify All behavior are unchanged.

Standalone integrity now enforces the independent 120,000-row candidate wall
while freezing that selection. Repository SQL applies fresh mode eligibility
before the limit; stale and completed rows form one deduplicated population;
saved resume validates every exact id and order. The first post-refresh excess
returns `FAILED+RAN` with the core-owned candidate fact's type and message,
without invoking the selection sink, verifier context, runner, hashing, or
outcome collection. Recorder open/close failure remains authoritative over a
simultaneous scale fact. Aggregate process-retention capacity remains a
separate dispatcher concern rather than a checkpoint wire model.

Inventory scan composition now requires the scanner's structural population
admission argument. The scanner checks each next domain/warning append and the
workflow validates the exact completed result before recording; initial valid
excess alone becomes `REFUSED+UNRUN`, while malformed output fails ordinarily.
General repository reads cap both raw request occurrences and returned rows.
Requested paths, row ids, and mapping identities stop before the first raw
excess and before normalization, validation, deduplication, or sorting; result
collectors stop before materializing the first excess typed snapshot. Integrity
validates the exact candidate-row tuple and then uses its ordinary
workflow-owned construction directly; there is no injected builder or duplicate
general row validator. Retained-byte authority remains unimplemented and must
surround the real construction graph.

Candidate filtering happens only while freezing a new integrity selection.
In the current implementation, baseline admits eligible non-directory rows
with no attestation; rebaseline
admits eligible rows that already have an attestation; verify retains both,
including null-attestation rows that must establish evidence and report
verification-incomplete. When a continuation already carries
`selection_item_ids`, resume reconstructs that exact ordered set without
reapplying mode filters. Completed ids/bytes and the original admitted order
therefore survive even if evidence changes after admission. A repeat full
baseline still performs
its required fresh inventory recording, but hashes and writes no integrity
attestation when every eligible row already has evidence.

The accepted but unrealized change admits null-attestation rows to fresh
rebaseline too, without weakening its explicit selected scope/acceptance or
changing resume selection. Rebaseline hashes and conditionally replaces or
creates evidence even when content matches; it clears verification freshness
rather than reporting a verified match. This admission change is not yet
implemented. See the [three-operation policy](VERIFIER.md#accepted-standalone-operation-policy)
for behavior and the [active M1 plan](M1_PLAN.md#remaining-checkpoints)
for delivery and regression requirements.

## Other Workflows

- History browsing is read-only and runs alongside mutating sessions.
- Replay reconstructs scope from retained detail and plans fresh.
- Undo/repair generates an ordinary plan and mandatory review.
- Database backup/check/export/import are typed maintenance sessions; app-owned
  mutation remains guarded/history-logged.
- Ingest follows [INGEST.md](INGEST.md) and the same two-session review boundary.
- Queue wakeup starts only an already reviewed/authorized execution set and
  freshly preflights; silent replan is forbidden. Contending commitments retain
  commit order, while disjoint-volume work may run concurrently.

## Error And Result Aggregation

Workflow catches typed module failures at the correct boundary, preserves
already-earned item/filesystem results, and lets the generic session runner
produce terminal. Filesystem, integrity, ledger `recording`, and history
`audit` statuses are independent. A verify-phase mismatch or exception never
rewrites successful execution; a ledger failure never suppresses byte
classification; a history failure/timeout degrades only `audit`. A contained
history receipt rejection also degrades audit while the observer continues to
record later events and terminal truth; an observer exception breaks the
prefix. The runner
drains and finalizes history first, settles the audit axis through the atomic
caller/pump ownership decision and actual pump outcome, and only then releases
the immutable Terminal.

Execution and integrity outcomes implement one nominal `ResultItem` contract
with explicit `item_type` and `phase` tags. Standalone Stage 3 sessions write
their ordered integrity items but no `history_phases` rows. Compound sessions add generic
`PhaseResult` summaries so a compound phase-wide failure before its first item
is not mistaken for empty success; transfer and readback byte counts remain
separate rather than being summed.

Result views keep the specific integrity axis visible. A hash mismatch receives
the higher `mismatch` headline; missing, modified/stale, unsupported, canceled,
or error items mean verification did not complete cleanly and cannot be
presented as success. A null-baseline item discovered during `phase=verify`
also receives `verification-incomplete` because it established a baseline
without performing a comparison; the same `baselined` result is successful in
an explicit baseline/rebaseline phase. One workflow-owned classifier applies
the exact precedence `failed > partial > refused > mismatch > canceled >
verification-incomplete > recording/audit degradation > all-noop > success`.
Live and reopened history views reuse it, while every lower-priority axis
remains independently renderable.

Live `all-noop` classification reconstructs effective selected kinds from item
kind plus the stable typed exclusion-reason set; excluded rows remain visible
but cannot make skipped non-noop work look like a selected no-op. The
current retained-history path reconstructs the same classification from
persisted item kind/outcome/reason, including `user-deselected`, after loading
the retained detail objects. Stage 6 replaces that summary path with grouped
SQL aggregation over those primitive columns and database-paged detail in
stable `item_order`; phase summaries remain whole.

Workflow result byte counters retain the central attempted-work meaning from
`ARCHITECTURE.md` §2.3. The execute projection uses its fixed reviewed budget
and aggregate high-water even when some streamed bytes were rolled back before
publication; standalone integrity uses physical-read work and its final
nondecreasing budget. A compound result exposes those domains in separate
phase summaries and projects execute at the top level rather than summing
copy and verification. Consumers must use reliable item outcomes, published
evidence, and ledger state—never the byte high-water—to infer durable content.

Paused compound execution continues from an explicit discriminated typed
checkpoint after fresh preflight. `phase=execute` carries execution status
and published evidence; `phase=verify` carries `PostCopySelection`'s transient
candidates plus completed ids/bytes, settled filesystem status, the execute
phase, compound-current recording, and ordered missing-evidence ids. Its phase
projection reconstructs the verifier's nondecreasing physical budget as
reviewed admission plus abandoned-attempt work and completed-stream overrun,
so terminal or resumed summaries cannot regress below emitted Progress. Frozen
`ExecutionSet.recording` remains execution truth; compound-current recording
may degrade later but cannot recover `DEGRADED` to `OK`. Resume never infers
phase from prior events or re-emits a completed reliable result. The compound
run's recorder may close at pause-drain and reopen the same token idempotently
on resume; it attempts finalization once after both entered phases settle, and
a finish failure degrades recording. Paused standalone
baseline/verify/rebaseline already use their exact candidate and item-status
checkpoint plus fresh remaining-selection guard. Unsupported pause requests
for inventory/plan/import are typed control rejections with no lifecycle
mutation.

The checkpoint is process-local custody state, not a durable recovery
format. Session storage contains metadata/results only, and
`InMemorySessionStore.load_all()` deliberately returns no sessions; closing
the process offers no execute/verify resume. A future durable metadata store
alone cannot restore that capability. A future durable-resume design would
require an explicit persistence boundary and schema; the current checkpoint is
not that format.

Refusal is distinct from failure and has zero managed-data mutation. Partial
failure derives from item outcomes, not merely whether any bytes moved. An
all-noop explicit run is completed/no-op and still history-worthy. A safe-subset
run can be filesystem `COMPLETED` with itemized `BLOCKED`/`DEFERRED` exclusions;
interfaces present that as partial completion rather than clean full success.
An all-skipped review refuses before admission because it contains no executable
work; it is not an all-noop run.

## Orthogonality Rules

- Planning preview does not create mappings or persist deletion policy.
- Plan invalidation does not clear inventory evidence.
- Inventory refresh does not rewrite attested baselines.
- Verification does not mutate plans or mark unverified noops.
- History does not record ledger truth or control work.
- UI choice does not alter workflow semantics.
- UI filtering/windowing does not alter folder scope, selection, or integrity
  candidate membership.
- Ingest source temporariness does not create role-bearing location state.

## Expectations

- Modules are callable and never import each other.
- Repositories return immutable snapshots and recorder is sole ledger writer.
- Dispatcher treats request/result as opaque and owns custody/control.
- Interfaces submit typed requests and present events/results; no interface
  reaches around workflow to call executor/SQL.
- Settings shaping a plan are snapshotted, not read opportunistically later.
- Fresh preflight observes filesystem/volume safety only; it never compares
  admitted intent with newer global defaults.

Workflow is the sole preflight owner: it sequences fresh observe → preflight →
scoped prior-run temp recovery → execute under custody on every start/resume.
Executor imports no sibling and performs only operation-local live precondition
guards.

## PoC Hardening

This sequencing prevents the unwired ledger, preview side effects, no-inventory
baseline/verify failure, target-role fallback, full refresh for selected verify,
missing integrity audit on unexpected exceptions, stale plan/inventory display,
and view-wide false verification scope. A common guard envelope prevents hash
import from handling refusal differently than baseline/verify.
