# Interfaces Layer

Status: M1 Stage 5.5's process-local `interfaces/service.py` facade, reviewed
sync/history adapter, explicit inventory/baseline/verify/rebaseline commands,
semantic-settings seam, revisioned selection, opaque-id location actions,
retry receipts, typed scan warnings, and final axis-preserving result
classification are implemented. M1 Stage 1's typed cosmetic UI-state owner,
two-row bridge channel, tested WebView2 security seam, classified launchers,
coordinated database-pair facade, secured product-host composition, and
hardened production transport and the persistent appearance override consumer
are implemented. `M1_BRIDGE.md` is the sole
normative bridge/BR-G authority. The installed real-WebView2 browser witnesses
and fixed, non-sliding
150 ms progress-only linger have landed. With an active long poll, the first
detailed progress snapshot may use that full interval; receipt and reliable
running-state feedback bypass that linger. Benchmark accounting now uses bounded
manifested streams, post-exit assembly, direct-Job child admission, and an
event-only pass separate from whole-runtime diagnostics. The frozen realistic
custody corpora and production-path runner have also landed. SH-G-8's realigned
event/custody evidence now includes a committed normative calibration-a
artifact, a frozen 1,966,080-byte ceiling, and an accepted independent
holdout-b dataset. That frozen v1 representation closes the historical
SH-G-8/BR-G-42 event-and-transport-custody claim. The historical v4
representation has separate diagnostic event evidence and Tier-1 custody drift
evidence; exact v5 now owns the current-source child and does not inherit or
alter the v1 acceptance. Other BR-G-42 rows, including
current-source event timing and later feature surfaces, remain open on their
owning slices. One current-source child runs as a separate ordinary-suite drift
guard and requires both live custody shapes to remain within the frozen
1,966,080-byte ceiling without modifying the accepted validator or artifacts.
The former BR-G-45 terminal-artifact model is retired by the initial
simplification run and supplies no aggregate-retention guarantee. Shell-owned
SH-G-15 whole-runtime containment remains independently open.
GUI Break 1 and Slice 4 completed their audited realignment and were hardened
and reverified on 2026-08-17; the user-facing
Setup, plan, inventory, integrity, and control surfaces remain. The history and
global-settings pages are deferred by the accepted second-half reslice. The gated desktop bridge
API and production mapping are active, while the current empty product page
invokes only startup and has no later workflow-surface callers yet.

The exact event-v5, scalar, recording, and database-epoch boundary is active.
Native directory admission, complete Setup, process-live desktop tasks, compact
artifacts, and bounded evidence reads remain accepted but unrealized. Exact
target contracts live in [M1_BRIDGE.md](M1_BRIDGE.md);
history/settings pages remain deferred.

## Purpose

Interfaces translate user/client intent into typed workflow submissions and
render dispatcher session state, events, plans, inventory, history, and results.
They own interaction behavior, validation feedback, and presentation state—not
sync policy, filesystem mutation, SQL, plan dependencies, integrity
classification, or session lifecycle.

CLI and desktop must produce the same workflow request for the same intent and
interpret the same typed result consistently. A future remote/non-bridge API
adapter, when added, follows the same rule.

## Service-Backed CLI Adapter

`interfaces/cli.py` is a thin service-backed adapter. It exposes reviewed
`sync`, read-only `history`, and explicit
`inventory`/`baseline`/`verify`/`rebaseline`; renders typed
plan/refusal/result/inventory views; requests cooperative cancellation on
Ctrl+C; and never imports core, modules, or the database layer. It does not
construct a dispatcher, registry, workflow request, or runtime directly. Human
confirmation occurs only after the plan session is terminal and closed. Both
real entry points consume `sys.argv[1:]`; before the desktop exists, no
subcommand prints usage and exits nonzero.

Plan review identifies the exact runnable selection plus blocked and deferred
items. A filesystem-completed safe subset is rendered as `completed with
exceptions` and returns the documented partial exit category; it is not
collapsed into either clean success or execution failure. Detailed history uses
the same outcome/reason fields. Rename-shaped review rows prefer the workflow
view's prior target path as their displayed origin, so recase, move, and
move-update approvals show the actual old-to-new target spelling.
For an irreversible in-place update, the CLI renders the authoritative risk in
the reviewed plan and treats the exact typed `execute` response as the
destructive acknowledgement. It never guesses acknowledgement from a truthy
adapter value.

The event-v5 terminal summary is intentionally item-free. For a healthy audit,
terminal sync and integrity rendering therefore reads canonical item pages
through the finalized fixed watermark; this preserves item order even when a
fast session finishes before observation begins. If audit is degraded, the CLI
falls back to the item events it actually observed and reports the independent
audit warning rather than inventing missing detail.

The implemented options and numeric exits are recorded in
[COMMANDLINE.md](COMMANDLINE.md). The service composition root registers
plan, execution, inventory, baseline, verify, and rebaseline with their exact
pause capabilities. Each location command supplies exactly one root or retained
location id plus an optional exact selected scope and ambiguity-resolving mount;
no adapter infers location from a mapping or another argument. Rebaseline also
requires an explicit selected scope and acceptance intent. Queue control,
machine output, and the desktop action layer remain deferred.

## M1 Shared Service

`interfaces/service.py` composes one process-local `LocalWorkflowRuntime`, the
domain-blind dispatcher, `SessionObserver`, the exact six-kind registration
table, sync
plan/review/commit sequencing, history access, controls, and primitive workflow
views. Runtime plan storage remains the existing process-local dictionary behind
named `save_plan`/`get_plan`/`drop_plan` methods; it is not a `PlanStore` and
does not survive process exit.

`_workflow_registry` is the single production workflow-registration surface.
It wires workflow-owned constructors and materializers to the detachment
contract in [DISPATCHER.md](DISPATCHER.md#public-contract). Constructors
establish the built-in checkpoints' ownership; public tests prove it. The
service adds no checkpoint certification or authority/adoption wrapper.

Every admitted execution, inventory, baseline, verify, or rebaseline session
also receives one exact process-local detail owner: the dispatcher session id
maps to either its execution run id or its inventory request id. Terminal detail
ownership is attached before dispatcher publication and is removed by the
admission rollback if publication fails, so shutdown cannot pass an admitted
but unowned detail session. Readback remains available until explicit session
close. `close_session()`
first waits for the dispatcher's exact worker/publication/audit retirement fence;
only a successful return removes that owner and drops the matching runtime
details, with the runtime drop performed after leaving dispatcher and service
locks. Timeout, self-close, and other dispatcher-close failures preserve both
objects for retry and cannot affect another session's details. Service shutdown
leaves all owners intact after an incomplete dispatcher result or failed runtime
close. A successful runtime close clears retained plans and execution-start
claims together with both detail maps, after which the service clears the now-
ownerless session relation. A dependency-close failure preserves all four maps
for the same serialized retry.

`start_plan` delegates root resolution to the shared workflow gate before
admission. That gate performs directory I/O with extended-length native
spelling but returns ordinary logical paths; the service neither imports core
path policy nor leaks `\\?\` through a plan, view, or missing-root diagnostic.
Distinct/nonnested validation therefore matches direct workflow callers even
when either absolute root exceeds the legacy Windows path limit.

`start_execution(request_id, *, verify_after_execute=False,
expected_revision=None, destructive_acknowledged=False, command_id=None)`
preserves the untouched M0/CLI default and opts into the Stage 4
execute→verify workflow only when requested. An omitted revision is valid only
for pristine revision-zero selection. Edited review state requires the current
revision; commitment transitions `reviewing → committing → committed`, with
admission failure restoring `reviewing`. At the direct service boundary, an
internal replacement of an artifact under one request resets user selection
and advances that request's revision monotonically, even when deterministic
operation ids repeat. Recognized selection command ids remain retry tombstones
across that replacement, so a lost response cannot reapply old intent to the
new artifact. The H2 desktop exposes no such in-task replacement: changed Setup
or explicit Plan again creates a new task, while the old plan slot stays
immutable. Plan again asks the backend to resolve the retained plan's reviewed
volume identities into fresh Setup slots; it never submits the old display path
or copies selection state. A refused/unrun execution reopens only the old task's
selection at a new revision, so subset retry remains a new commitment over the
same plan rather than artifact replacement.
Folder gestures expand only toggleable descendants; a
safety-disabled row remains disabled without making selectable siblings inert.
Only the execution registration supplies
`settle_canceled=runtime.settle_canceled_execution`; the service does not decode
continuations or decide cancellation policy. Retained `HistoryRunSummaryView`
exposes primitive lifecycle/watermark fields, filesystem/integrity/recording/
audit axes, disposition, cancellation, headline, counts, and bounded phases,
using the same workflow classification source as live result views. Ordered
canonical items and reliable receipts are separate bounded page views; a
`HistoryEventView` exposes sequence/time/schema/body type,
disposition/hash/link/rejection metadata, and an optional body rather than
fabricating a live session event for a hash-only receipt. All detail readback
remains page-bounded. Every current event view requires nested schema version 5;
byte/size/nanosecond fields in public views are canonical `Scalar64` strings,
while counts, cursors, and revisions remain exact JavaScript-safe integers.
Packaged public result and terminal-record validation checks compound
cancellation, recording, and review facts against its surviving closed
vocabularies; their exact meanings remain in [CORE.md](CORE.md). Live event
bodies are supported Python producer projections rather than a second browser
schema. Required Node coverage sends all seven production event projections
through the public consumer and keeps public result/record negative cases. The
required drain probe separately owns transport/reducer behavior.

The browser has one live-event transport check,
`validateLiveSessionEvent`: an exact wrapper, matching session, positive
SafeInt sequence, current v5 marker, recognized tag, and plain-object body. It
does not mirror Python body vocabularies, timestamp grammar, cross-field rules,
or reliable-byte accounting. The drain still validates update unions, strict
sequence order, Gap recovery cursors, terminal ordering, batch capacity, and
reducer transitions before any callback or cursor mutation. The consolidation
audit found no surviving legacy helper or semantic twin, and live
task events reject a retired transport version without advancing the cursor.

Session-record timestamps use CORE's exact UTC service grammar at the external
browser boundary. Live event timestamps are producer-owned. The reliable-event
byte wall is enforced once by `canonical_event_bytes` before EventHub mutation;
ASCII and mixed-Unicode exact-maximum/plus-one cases prove its UTF-8 accounting.
Persistence readback retains exact timestamp, Unicode, scalar, and cross-field
validation. Browser whole-batch refusal remains for transport, ordering,
lifecycle, and reducer failures, with clean replay of previously unaccepted
updates.

The current public service surface includes:

```python
NamiSyncService(ledger_path, history_path, *, settings_path=None)
validate_database_contracts() -> DatabaseContractView
initialize_database_contracts() -> DatabaseContractView
start_plan(source, target, *, deletion_policy=None, command_id=None)
    -> PlanSession
start_task_plan(source, target, *, deletion_policy, command_id,
                delivery_factory) -> TaskStartView
reobserve(session_id, sink, from_sequence) -> SessionRecordView
unsubscribe(session_id) -> None
close_session(session_id) -> None
drop_plan(request_id) -> None
preview_selection(request_id) -> SelectionPreviewView
mutate_selection(request_id, expected_revision, *,
                 deselect=(), reselect=(), command_id=None)
    -> SelectionMutationView
start_execution(request_id, *, verify_after_execute=False,
                expected_revision=None, destructive_acknowledged=False,
                command_id=None)
    -> ExecutionSession | ExecutionAdmissionView
start_inventory(*, root_path=None, location_id=None,
                selected_paths=(), selected_mount=None,
                selected_ids=None, command_id=None) -> LocationSession
start_baseline(*, root_path=None, location_id=None,
               selected_paths=(), selected_mount=None,
               selected_ids=None, command_id=None) -> LocationSession
start_verify(*, root_path=None, location_id=None,
             selected_paths=(), selected_mount=None,
             selected_ids=None, command_id=None) -> LocationSession
start_rebaseline(*, root_path=None, location_id=None,
                 selected_paths=(), selected_mount=None,
                 selected_ids=None, command_id=None) -> LocationSession
reobserve_task(task_id, session_id, sink, from_sequence)
    -> SessionRecordView
release_task_session(task_id, session_id, delivery)
    -> TaskSessionReleaseView
close_task(task_id, session_id, delivery) -> TaskCloseView
list_unacknowledged_missing(location_id) -> tuple[InventoryRowView, ...]
list_stale_inventory(location_id, verified_before) -> tuple[InventoryRowView, ...]
acknowledge_inventory(command_id, location_id, row_ids, *, changed_at)
    -> tuple[InventoryDispositionView, ...]
restore_inventory(command_id, location_id, row_ids, *, changed_at)
    -> tuple[InventoryDispositionView, ...]
read_semantic_settings() -> SemanticSettingsView
commit_semantic_settings(patch: SemanticSettingsPatchView) -> SemanticSettingsView
list_history(limit=50) -> tuple[HistoryRunSummaryView, ...]
get_history_summary(run_token) -> HistoryRunSummaryView
get_history_items(run_token, *, after_order=0, through_order=None, limit=256)
    -> HistoryItemPageView
get_history_events(run_token, *, after_seq=0, through_seq=None, limit=256)
    -> HistoryEventPageView
```

The plan/session lifecycle deliberately has two live service surfaces. The
session-oriented family is `start_plan`, `reobserve`, `unsubscribe`,
`close_session`, and `drop_plan`; the CLI currently calls `start_plan`,
`unsubscribe`, and `close_session`, while the other two remain supported direct
service operations. The task-bound family is `start_task_plan`,
`reobserve_task`, `release_task_session`, and `close_task`; the desktop bridge
reaches only those four through `TaskLifecyclePort`. Neither family is dead
code. Both delegate to the same application authority: starts use the
`TaskLifecycle` command/admission path, both reobservation forms share
`_reobserve_session`, session/task settlement shares `_settle_session`, and
direct plan drop uses the same exact plan-retirement owner as task settlement.

### Task lifecycle ownership

Exact wire, scalar, task-authority, population, and retention contracts live in
[M1_BRIDGE.md](M1_BRIDGE.md) and [DEFENSE.md](DEFENSE.md).

Workflow owns parsing, fresh admission, and canonical Setup. The application
lifecycle owns command effects, domain-effect receipts, exact task/session
association, compensation, and logical settlement. Every admitted session,
including a direct CLI session without a desktop task, receives an application
association. Dispatcher independently owns session admission, custody,
concurrency, control, and close. The service-owned `SessionObserver` is
implemented in `interfaces/session_observer.py`; it alone owns adopted stream,
callback, thread, and subscription lifetime. External release waits for every
retained worker. Callback self-release skips self-join but leaves the exact
physical subscription observer-owned until that callback unwinds, so a
concurrent external release can still wait truthfully.

The adapter owns only bounded intent and response replay plus queue, drain,
connection, delivery-generation, terminal-delivery, and presentation state.
Its process-live task binds at most one current session and keeps a published
H2 plan immutable without inventing domain lifecycle or volume locks.

Only complete review generations and compact overlays become task state.
Terminal reconciliation repairs delivery gaps; full result items and transient
hashes never enter JavaScript. Server projections own hierarchy, scope, paging,
and framing. Task reads rehydrate the UI, exact release removes session custody,
and close destroys task presentation/receipts. Interfaces follow and recheck
bridge authority around outside work.

The accepted but unrealized contract adds shared plan/inventory sibling sorting
to those server projections. New views and reset use canonical path-key order;
explicit filename/size/mtime choices reorder presentation before windowing, not
domain selection, recursive scope, or execution authority/order. Raw workflow-
owned sort facts and complete production command/validator support must be
active whenever sorting activates, even if mtime/reset GUI layout remains
latent. Revisions, indexes, anchors, and late-response guards move coherently
under the exact
[Bridge sorting contract](M1_BRIDGE.md#sibling-sorting-accepted-checkpoints-7-and-9).

External values are validated before presentation construction. Numeric
encoding follows bridge/defense domains and identity remains non-arithmetic.
Execution evidence is an atomic ledger view, never later-start authority; exact
classification lives in the bridge and [DATABASE.md](DATABASE.md).

`DatabaseContractView` contains only primitive `state`, `reason`, and
`reset_direction` fields. Its validation method is strictly read-only and
classifies the ledger/history mains plus WAL/SHM/journal sidecars as fresh,
ready, or refused. Initialization is a separate call and never resets an
existing file. Sync and location CLI compositions validate before their first
admission; fresh sync review remains database-free until execution commitment.
Execution, inventory, integrity, and direct inventory-visibility mutations
revalidate and ensure the pair before any history observer can open. The
standalone read-only history composition intentionally does not require or
create its missing ledger peer.

History summary/page limits are `1..256`. Omitting `through_order` or
`through_seq` starts a fresh traversal and captures the current durable
watermark in the read transaction; callers reuse that returned watermark on
later pages for a stable prefix while recording continues. Caller-supplied event
watermarks are inclusive upper bounds in a sequence space where omitted lossy
events create legitimate gaps. Pages decode and return at most the requested
limit; an indexed lookahead decides whether more reliable events exist.
Summaries decode no event payloads and may represent a nonterminal run as
`completion_status="incomplete"`, with nullable terminal axes plus its current
state, phase, committed sequence, item count, and commit time. After a restart
the service exposes that committed prefix as incomplete; it does not infer
`INTERRUPTED` or claim execution resumability without M2 custody.

If a fresh event traversal's `after_seq` is ahead of the durable window, its
empty page reports the durable `through_seq`, preserves the supplied cursor as
`next_after_seq`, and sets `has_more=False`. That traversal is complete; a later
check omits `through_seq` again rather than combining the older watermark with
the preserved cursor. Explicitly supplying a watermark below `after_seq`
remains invalid. Every request also verifies the run's official maximum event
sequence, even when traversing an older fixed watermark.

Reliable-event pages are the catch-up source after an ordinary subscriber
reports `Gap`: retain the last successfully applied non-`Gap` sequence rather
than the synthetic `Gap` envelope's sequence, fetch through one fixed committed
sequence, apply available recorded/duplicate envelopes by sequence, report any
hash-only rejection receipt, consult the summary for
terminal truth, then resubscribe after the watermark, repeating with a fresh
traversal if live replay or durability advanced again. Missing sequence numbers
may be lossy `Progress` events, which history deliberately does not retain, and
are not themselves durable history loss.

Location starts bind the five-state resolution synchronously before dispatcher
admission and return a primitive `LocationSession`. An unresolved binding raises
`LocationResolutionError` with a `LocationResolutionView`; the adapter renders
offline, ambiguous, missing-root, and unavailable-root guidance without
starting work. `LocationResolutionView` carries primitive state, root/id,
selected mount, candidates, and detail.
`InventoryDetailsView` adds request/scope, observed/missing counts,
completeness, and primitive typed warnings. `InventoryRowView` carries
primitive path/presence/evidence fields. `list_inventory()`,
`list_unacknowledged_missing()`, `list_stale_inventory()`, and
`mapping_ids_for_location()` expose role-free reads without leaking
repositories or domain objects. Visibility mutations return the recorder's
typed disposition per row; a retry reuses the gesture id, derived per-row
receipt ids, and the original UTC timestamp.

The id-based location form rejects an explicit empty collection and ids from a
different location. Row ids remain exact subjects. Folder node ids resolve
through the location-scoped workflow tree using the bridge-owned opaque codec.
Refresh carries a recursive subtree root so it can discover new descendants,
while integrity freezes the indexed subtree to exact paths before admission.
Path-based CLI calls retain their existing full/exact behavior.
If a queued or resumed activity becomes unresolved at wake-up, its retained
`InventoryDetailsView` carries the same state/candidates and the CLI renders the
same corrective guidance. A provisional ambiguous binding exposes no selected
mount; only an actual prior explicit choice is reported as selected.

Session-creating plan, execution, inventory, and integrity commands use bounded
command-id stripes for same-command single flight while disjoint commands may
enter lower application work concurrently. `TaskLifecycle` is the sole
domain-effect receipt authority and owns exact session associations; Dispatcher
custody is not a receipt lifetime. Every admitted direct or task-bound session
receives an application association before publication.

Direct start receipts retire after successful direct `close_session`. A task
start receipt survives terminal-session release and retires only at task close.
Selection-mutation receipts survive artifact replacement and retire with the
exact plan on `drop_plan` or service shutdown. Other application receipts retire
with their owning session, plan, task, or service shutdown. Receipt lookup joins
an active direct close or full task close rather than replaying a closing
session; task replay remains available during terminal-session release.

The adapter may independently retain bounded transport-response replay for
`start_plan`. One entry contains only command id, wire intent, in-flight/result
delivery state, and an exact `TaskStartView`; it contains no resolved root,
session association, compensation, observer resource, or cleanup authority. A
retained successful response may therefore replay before resolving expired or
evicted source/target slots. A fresh resolution refusal for which no response is
retained creates no application receipt, association, observer, or dispatcher
session; refusal replay is not cached.

`TaskLifecyclePort` exposes only task-bound start with a presentation delivery
factory, exact task/session reobservation, terminal-session release, and task
close. The application mints the task id and supplies it to the factory before
dispatcher admission. The factory may create provisional adapter queue state;
its own call frame discards that state on failure, and no application or service
rollback refers back into the adapter.

A task-bound release consumes a truthful adapter terminal-delivery fact, advances
application settlement, confirms service-observer release, closes Dispatcher
custody, retires the exact runtime detail, and only then optionally retires the
plan/task. The fixed cleanup owners are independently idempotent or monotone.
The durable owner-call contract is: settlement may repeat exact-owner calls,
but each exact physical transition and observable effect occurs at most once.
After failure or interruption, the whole cleanup call sequence may repeat from
current owner truth. The
observer and runtime detail/plan owners accept repeated exact-subject absence;
Dispatcher close remains strict, and only a sealed exact application settlement
interprets `SessionNotFound` as custody already absent. Plan retirement uses one
tolerant exact-token claim: a retired token produces no new work, while active
mutation and retirement remain mutually exclusive. `TaskLifecycle.publish_start`
deliberately does not wait for plan retirement. Fresh service-minted plan
request ids are not intentionally reused by supported callers, so a live or
retiring collision fails fast instead of treating the id as a reusable key. The
application retains the exact association, terminal digest, settlement target,
and one coarse single-flight claim, never physical-step acknowledgements or
cursors, a sink, stream, callback, observer thread, queue, drain, connection,
delivery generation, or bridge response.

The web drain owns response replay, its 64-update queue, backpressure, drain
claims, generations, connection state, and terminal-delivery receipt. Delivery
shutdown marks delivery closed, invalidates generations, supersedes drains, and
wakes blocked offers before service observer release. It never owns observer
release, dispatcher/session close, detail retirement, plan drop, or
compensation. The strong import contract `Web task drain cannot reach domain
lifecycle owners` forbids both direct and indirect drain paths to those owners,
including `SessionObserver`.
The application admits at most 48 active desktop task effects before invoking a
delivery factory or lower application work. Independently, the adapter keeps at
most 48 successful/in-flight start-response entries, retiring successful entries
with their tasks, and 48 close-response tombstones with least-recently-used
eviction. These are exact count bounds and make no retained-byte or whole-runtime
memory claim.

Plan task records retain the workflow's exact `sync-plan` kind across the
service and browser boundary; retained database history remains independent of
task presentation cleanup.

The active plan-task adapter retains exact view types, task/session identity,
exact-integer positive event sequences, wrapper/batch/order/lifecycle checks,
and terminal record/result validation. The bridge response snapshot is the
sole Python-side pre-serialization adapter enforcer of the JavaScript-safe
upper bound; browser transport admission independently retains PositiveSafeInt,
and core envelopes already construct sequences in that domain. The adapter
does not recertify trusted event-body semantics at offer, recovery, drain,
command return, or bridge serialization. A
drain constructs and validates its complete candidate before popping queued
updates, clearing a pending terminal, or earning a terminal-delivery receipt. A
terminal record
update must carry a non-null valid result agreeing with its lifecycle state;
both Python and the packaged browser refuse result-free or malformed updates.
Bare result-free re-observation snapshots remain valid but cannot earn that
receipt. Explicit replay still invalidates its uncertain observation generation;
it does not revoke a previously earned delivery receipt. Release consumes that
receipt even if replay has cleared the transient terminal cache. Browser batch
refusal precedes callbacks, cursor/reducer advancement, and release; successful
terminal presentation remains required before the browser requests release.
Failed single-flight starts retain only a closed four-value failure code for
observation conflict, task unavailability, interruption, or generic start
failure. Every participant and retained failure replay receives a fresh fixed
exception without chaining; the initiating exception and any domain-cleanup
failure, including message, type, traceback, cause, context, and attached graph,
never enter adapter state.
Explicit observation recovery applies the same closed-boundary rule before it
reacquires the task condition: a reobserve, validation, or stale-result
failure becomes one of four fixed recovery codes, its traceback/cause/context
and any unadmitted current view are dropped, and generation invalidation and
queue truth use only that code. Ordinary failures return a fresh fixed
`RuntimeError`, known conflict/unavailability retains its public category, and
`KeyboardInterrupt`, `SystemExit`, and `GeneratorExit` each return a fresh fixed
`KeyboardInterrupt`. A stale successful recovery cannot grant the drain raw
unsubscribe authority; service-owned observation release remains part of the
high-level application release path. Adapter retry state contains only its
fixed public failure code and transport progress, never compensation or
domain-cleanup flags.

The application admission token owns the exact partial-admission liabilities:
session association, detail installation, observer adoption or stream
retirement, and dispatcher publication after attachment. A coarse single-flight
claim excludes concurrent rollback for the same exact admission. Physical work
runs outside the lifecycle condition; after failure or interruption, cleanup
abandons the claim and a retry may replay the whole fixed cleanup sequence from
current owner truth. Calls may repeat, while completed observable effects remain
unique. Initiating and cleanup exception graphs are retired before a fixed
failure escapes. The service's ordinary path-refusal wrapper likewise clears
the workflow validation graph before raising the existing unchained
`SyncPathInputError`; bridge and host code retain only their final adapter
failure frame.

Dispatcher's existing `_AdmissionCleanup` remains unchanged. The application
cleanup contract does not claim recovery across the inherited gap between
`Dispatcher.submit` returning and application start publication; closing that
gap requires separate dispatcher/application reconciliation.

The runtime owns `SemanticSettingsStore`; the service accepts optional
keyword-only `settings_path` but imports no database package. Its default is
`settings.json` beside the selected ledger. `read_semantic_settings()` and
`commit_semantic_settings(SemanticSettingsPatchView)` expose only primitive
workflow views: filters, deletion policy, trash-on-update, preservation
booleans, and source-casing propagation. A partial patch preserves omitted
fields. Public view construction requires exact booleans, tuple-of-string
filters, a supported deletion value, and the correct preservation view, so an
invalid patch cannot poison the atomic settings file.
The currently active `start_plan(..., deletion_policy=None)` captures the
complete stored snapshot once; an explicit deletion override changes only that
plan, and review exposes the complete frozen snapshot while commit/execution
never reread settings. At the accepted desktop Setup cutover, the bridge
submits one complete raw Setup value and freezes only the backend-derived
canonical snapshot. It leaves global settings unchanged; exact Setup fields
remain bridge authority.

`classify_result(OperationResultView)` returns a primitive
`ResultClassificationView` containing the workflow-owned headline and the
independent filesystem, integrity, recording, audit, disposition, and
cancellation values. The CLI
uses only that headline for its numeric exit and continues rendering every
secondary axis. It never rebuilds domain lists by attribute shape or parses a
diagnostic string.

`SessionObserver.observe(session_id, sink)` performs a synchronous
get-before-subscribe check, returns an already-terminal view without opening a
stream, and otherwise forwards only primitive session event/record views to the
sink. Its worker blocks on `EventStream.next()` without polling, recovers an
ejected stream from the first undelivered sequence, and never exposes the raw
stream. Any worker `BaseException`, including stream-close failure, retains only
a Boolean and `wait()` raises a fresh fixed `RuntimeError` without chaining or
invoking `threading.excepthook`. Each observation
retains only its current stream; recovery temporarily
owns the previous stream and its replacement, then closes and releases the
retired stream without accumulating a history. Stop, observation identity, and
replacement adoption share the observer lock. Cleanup snapshots current streams
under that same lock, while every stream close and worker join runs outside it.
Every snapshotted stream receives an independent close attempt even if an
earlier close raises `BaseException`; cleanup still joins and retires all stopped
observations before exposing one fresh fixed unchained cleanup failure. A stream
that remains live after its failed close retains the observation only through
the existing bounded join-timeout retry path. `SessionObserver.close()` retires
its completed observation snapshot and loop alias before raising a fresh fixed
cleanup error. An unexpected ordinary join failure follows that fixed path;
an unexpected join `KeyboardInterrupt`, `SystemExit`, or `GeneratorExit` becomes
a fresh fixed `KeyboardInterrupt`, and a join timeout remains a fresh fixed
`TimeoutError`. Stopped observations are retired in every case, while only live
observations remain for retry. Adoption closes an offer that it cannot retain
and returns no rollback or cleanup capability; an accepted subscription can be
released only through `SessionObserver`. Neither `TaskLifecycle` nor an adapter
retains observer cleanup authority. The service
converts any observer close exception to one ordinary/interrupted
Boolean before dispatcher and runtime shutdown, clears its
traceback/cause/context without formatting it, then raises a fresh fixed
`RuntimeError` or `KeyboardInterrupt` in the same categories. Observer retry,
cached dispatcher success, runtime-close ordering, and incomplete-shutdown
truth are unchanged.
Reobservation uses an explicit positive-first-desired-sequence seam. A
task-bound plan start transfers its factory-created sink directly to the
service observer during admission; direct CLI starts remain session-oriented
and observe afterward. In both forms the sink is excluded from receipt identity,
and attach failure or a shutdown race rolls back the unpublished application
liabilities and starts no work. Unsubscribe delegates only to the service
observer, which closes the current stream before joining its worker; a racing
replacement is either included in that cleanup or rejected and closed by the
worker. Service shutdown closes all observer streams and joins all observer
threads before
dispatcher shutdown, then closes the workflow runtime last so audit finalization
cannot reach a closed history store. A join timeout retains the unjoined
observation and makes the service close fail; later close retries that join, and
cached success is unavailable until it completes. If dispatcher shutdown
reaches its deadline with unfinished custody or observer work, the service
leaves the runtime open and a later `close()` retries shutdown. A complete
dispatcher result is cached,
but the overall close becomes final/cacheable only after runtime dependency
closure also succeeds; a dependency-close exception leaves its store retained
and a later serialized `close()` retries that step without repeating dispatcher
shutdown. The runtime serializes its own store-close attempt as well, so a
concurrent caller cannot return success before an earlier close fails. Once the
first shutdown attempt begins,
the domain facade rejects new starts, plan/selection/settings/inventory/history
access, mutations, and new observation even when dependencies remain open for
settlement. Existing session status, control, unsubscribe/wait, explicit
session close, and the shutdown retry remain available for cleanup.

`cli` and `web` occupy one import-linter layer above `service`: neither adapter
may import the other, and the service may import neither adapter. Stage 6 adds
`interfaces.launcher` as the top layer. Its console and GUI functions import
only the selected sibling lazily, so explicit CLI work never imports pywebview.
The `interfaces` package initializer preserves its public `main` entry point
through a lazy wrapper.

## M1 Stage 1 Desktop Foundations

`DEFENSE.md` owns the desktop trusted-base and tolerance policy;
`M1_BRIDGE.md` owns the exact transport mechanisms and acceptance gates below
it. This document records their interface-layer implementation.

Task-registry construction has no model-specific Python patch, build, GIL, or
allocator admission. Distribution metadata declares only the Python 3.13 lower
bound; exact runtime profiles remain evidence qualifiers rather than startup
gates. Any future representation-dependent predicate must land atomically with
its accepted model, validator, and evidence.

The replacement for the unused `interfaces/ui_state.py` prototype now owns
strict-shape `ui-state.json` independently from database-owned
semantic defaults. Schema v1 contains only the typed appearance section and
its `system`, `light`, or `dark` value. Ledger-derived recents never enter this
file; geometry, column, treegrid expansion/grouping, and filter persistence
require later typed schema additions. H2 sorting is process-live view state;
durable sort preferences are excluded from M1.
The owner bounds the file before decoding, refuses duplicate or unknown
members, and never rewrites during load. Missing state yields clean defaults;
malformed current state yields dirty session defaults; a newer unsupported
document or section value is additionally persistence-blocked so an older
binary cannot destroy it. An existing artifact that cannot be read is also
persistence-blocked so close cannot overwrite uninspected content. Explicit
guarded replacements update memory and
subscribers immediately, then schedule a 250 ms process-local coalescing
writer. Each scheduled document generation gets at most one serialized atomic
attempt; failures remain dirty and emit only a stable diagnostic plus exception
type. Close waits an in-flight write and flushes only a current dirty document
generation that has never been attempted, never a failed or unsupported one.
Cross-process semantic write coordination remains in the database settings
store and is deliberately not implied for cosmetics.
This typed owner lifecycle, its exact read/replace bridge rows, and the
appearance consumer are active.

`interfaces/web/bridge.py` owns the promoted security-sensitive host boundary;
the product window composes it without changing the proven guard behavior. The
supported host dependency is pinned to the
reality-tested pywebview 6.2.1. That exact pin is security-relevant:
pywebview internally returns exposed-function results through
`webview.util.js_bridge_call` and `Window.evaluate_js`, so any version change
must re-audit that serialization/escaping path and rerun the real-WebView2
hostile-name round trip. Before `create_window`, host preparation pins
`OPEN_EXTERNAL_LINKS_IN_BROWSER=False`, `ALLOW_FILE_URLS=False`,
`ALLOW_DOWNLOADS=False`, and `REMOTE_DEBUGGING_PORT=None`, passes
`debug=False`, and performs a read-only registry probe for the WebView2 runtime.

Native exposed calls retain their admitted handler position through both the
actual pywebview worker's exit and an exact browser receipt sent after detached
JSON cloning. The host selects that lifetime explicitly; ordinary direct
`dispatch` calls still release their position when the call returns. A reload
advances one bridge generation and retires earlier browser custody atomically,
including entries paused before reservation. Shutdown joins exact worker
objects outside the bridge lock; an expired close deadline retains the position
and leaves close retryable. This bounds admitted return custody, not pywebview's
pre-admission thread creation, renderer allocation, or representation-specific
copy bytes. The former BR-G-45 aggregate-retention model is retired; any future
task-surface containment contract requires a new finite delivery register.
Before exposing the bridge, the host installs a per-window callback registry
that discards only pywebview's unused synchronous `None` entries. Callable
asynchronous entries keep their upstream lookup/delete behavior. Pinned-source
tests own both the worker lifetime and the absence of a reader for those
synchronous entries; a dependency change must revalidate them.

`interfaces/web/host.py` owns the per-logon single-instance primitive. The
production identity is always `Local\NamiSync.Desktop` with activation title
`NamiSync`; neither product version, nickname, data root, argv, environment,
nor page state can select a different namespace. Tests inject private identities
only through Python construction.

The same construction boundary may replace the packaged index with one
existing absolute physical local file for native probes and the non-shipped
component gallery. Production launch always resolves package data and offers no
index override through argv, environment, page state, or bridge traffic.

Phase 0 now supplies the dependency-free runtime version source, injectable
`%LOCALAPPDATA%\NamiSync` path set, and rotating file logging shared by the
`namisync` and `pywebview` loggers before pywebview import. Startup diagnostics
use the product `VERSION` only; the human-facing release nickname is never log
or compatibility authority. Pythonnet 3.1.0 is an
exact Windows dependency because delegate subscription, WinForms thread
marshaling, and `CoreWebView2` access are part of the proven boundary. Bottle
has a floor of 0.13.4. The supported pythonnet runtime is its default Windows
.NET Framework (`netfx`) path, so the existing read-only .NET Framework probe
covers both native-host prerequisites. An unset `PYTHONNET_RUNTIME` or the exact
`netfx` value is accepted; any conflicting override is refused before native
host preparation. The product WebView2 data directory is
the explicit `%LOCALAPPDATA%\NamiSync\webview2` path, not pywebview's temporary
private-mode default.
GUI roots are resolved to a physical local drive: UNC and mapped-network roots
are refused, and a pre-existing child junction may not redirect any database,
settings, log, UI-state, or WebView2 artifact outside that resolved root.
The headed host then holds non-reparse, delete-denying handles on the app root,
logs and WebView2 directories, plus both ready database mains, for process
lifetime and revalidates the pair after binding. Second-instance activation
requires the title-matched HWND's process image to match `sys.executable` or the
venv base interpreter. The predictable named mutex remains a UX primitive and
cannot prevent a malicious same-principal process from squatting its name or
spoofing an accepted base interpreter.
The side-effect-free compatibility module mirrors pinned pywebview 6.2.1's
.NET prerequisite, accepted Edge channels, and HKCU/HKLM architecture routing;
behavioral parity tests execute the upstream detector functions without
importing WinForms. Its `86.0.622.0` token is the exact argument used by the
pinned backend's compatibility helper; the mirror preserves that helper's
actual comparison and does not claim current security patching. A configured
`WEBVIEW2_RUNTIME_PATH` short-circuits only Edge-channel discovery; the shared
.NET/netfx prerequisite is still read once. One typed probe result carries
availability and the refusal reason from the same registry snapshot; host
preparation does not repeat the .NET read to choose a message. Missing .NET or
WebView2 receives its specific install action, while malformed or unreadable
registry state is a detection failure with a repair action. The start
wrapper repeats preparation before explicitly requesting `gui="edgechromium"`.
This refuses absence before pywebview can import its registry-mutating MSHTML
fallback. A refusal names the prerequisite it actually found missing: an absent
.NET Framework release key reports .NET 4.6.2 rather than blaming WebView2.
That state is also the mirror's one deliberate divergence — pinned upstream
raises `UnboundLocalError` from a `finally` closing a never-bound key, while
the mirror refuses cleanly — and it is unreachable on Windows 11, which ships
.NET Framework 4.8 in-box. A synchronous `initialized` check still refuses any
non-Edge result with an actionable message; unrelated startup exceptions retain
their original diagnosis.

The live Windows spike established two constraints that the earlier mock did
not represent. First, pywebview runs its setup callback and exposed functions
off the WinForms UI thread; reading `CoreWebView2` there can deadlock rather
than raise. Before startup the start wrapper registers one composed
zero-argument `initialized` callback: it verifies the renderer first and only
then invokes host initialization, so an MSHTML refusal cannot run native
security setup. After the asset server has selected its loopback port, the host
callback derives the exact origin from the complete `window.real_url` with
`urlsplit`, without string trimming, and registers one idempotent installer on
pywebview's synchronous `before_load` event. The `before_load` callback runs on
the UI thread and attaches `NavigationStarting`, `FrameNavigationStarting`,
`NewWindowRequested`, and `SourceChanged` exactly once before pywebview
exposes application calls. Attachment state is explicit and sticky: dispatch
fails closed before attachment or after failure, while the headed host must
turn a recorded failure into an actionable teardown instead of leaving a dead
window open.
Second, after native cancellation, pywebview's managed `Source` and
`get_current_url()` can report the rejected target even though
`CoreWebView2.Source` and the active document remain at the packaged origin.
The native callbacks consequently maintain a lock-protected committed-source
snapshot, and `dispatch` rechecks that snapshot without crossing into the UI
thread. A canceled target never replaces it; a genuinely committed off-origin
native source does and makes dispatch fail closed.

Pywebview receives no bridge object graph: the host passes `js_api=None` and
exposes one versioned, size-bounded, allowlisted function named `dispatch`.
It rechecks the native committed origin on every call, accepts one
strict JSON request object, rejects duplicate keys, non-integer schema
discriminators, and invalid Unicode, and returns a JSON-safe structured result.
Each pywebview injection starts a host-owned closed document generation. The
fixed `shell_ready` and `readiness_echo` rows are the only bootstrap-phase
commands; composition captures that generation with admission and rejects a
stale invocation context. Normal rows become available only after native load,
packaged receiver/DOM acknowledgement, safe initial window-surface settlement,
and a neutral host challenge successfully posted to and echoed by that current
document. The 32-lowercase-hex challenge is a current-generation liveness nonce,
not authorization; it is never logged or persisted and does not replace native
exact-origin trust. Reinjection repeats the bilateral exchange through the same
sole `dispatch` function, while terminal gate states expose no readiness
context. After open, composition permits only `readiness_echo` replay in a
bootstrap context so a delivery-uncertain page can learn the truthful open
result; `shell_ready` remains unavailable. Normal calls, retries, and retained
task drains remain paused until the echo is acknowledged.
`interfaces/web/readiness.py` owns this exact current-document state machine,
its deadline and terminal states, and its immutable `ReadinessContext` values.
The host binds native, shell, safe-surface, neutral-post, open, and refusal
callbacks to that owner. Appearance observation and publication are a separate
degradable axis after surface safety settles. Each immutable command row
declares only a `BOOTSTRAP` or `OPEN` phase. Host composition owns
`admit(name)`: it joins the
row from the final command mapping to the current exact context and returns the
bridge's generic `AdmissionGranted(context)` or `AdmissionRefused` carrier.
The bridge exact-checks that carrier, otherwise fails as `bridge_unavailable`,
and forwards a granted context opaquely. `CommandSpec.invoke` independently
exact-checks the context and phase before payload validation. Exact-document
trust and the bridge's 64-handler reservation remain transport-owned; service
session admission remains a separate domain-blind dispatcher concern.
`interfaces/web/document_channel.py` alone canonicalizes, bounds, schedules,
currentness-checks, and posts production WebView2 messages. Production reuses
one acknowledgment-enabled channel across document generations. It owns at
most one sent post awaiting acknowledgment, one queued required readiness post,
one queued replaceable appearance post, and one queued native dispatch. A
required acknowledgment is exactly a JavaScript-safe generation plus a
32-lowercase-hex challenge; a replaceable acknowledgment is exactly one
nonnegative JavaScript-safe presentation revision. Replacement and close
invalidate the document epoch and terminally complete stale owners; repeated
replacement cannot enqueue another native dispatch. The final epoch check and
`PostWebMessageAsJson` are atomic under the channel gate, using the pinned
non-reentrancy premise in `DEFENSE.md`. Local nonproduction callers that do not
request acknowledgment retain the ordinary independent-post behavior.
Appearance and readiness share that sink without sharing domain state.
Production revokes appearance publication before every document replacement
and enables it only after the current readiness challenge opens the desktop,
so an appearance acknowledgment can never be required to make readiness
reachable.
NamiSync application code never constructs JavaScript or calls `evaluate_js`,
`run_js`, or `Window.state` to carry application data. Pinned pywebview does
construct JavaScript internally for its exposed-function return transport;
its escaping is therefore inside the tested security boundary, not evidence
that the transport is system-wide script-free. The implemented host preserves
the NamiSync-owned shape and strict shared text sink; Slice 3 implements the
bounded/coalesced event drain, while Slices 5 and 6 add the production plan and
inventory DOM renderers.

The interface keeps filename display as exact valid Unicode through workflow
views, visible-sequence derivation, wire encoding, and literal case-folded
search. Only the final filesystem-label renderer maps `DEFENSE.md`'s fixed
layout-control set and input marker delimiters to injective `⟦U+XXXX⟧` text,
then delegates to the generic `textContent` sink. It imposes no extra field
cap. Tree callbacks carry the unchanged opaque node id, never a decoded marker
or display path. CSS bidi isolation contains ordinary directional text without
rewriting Arabic, Hebrew, combining sequences, emoji/variation selectors,
ZWNJ/ZWJ, or long labels.

The sole presentation-only native-to-page path is the existing system-
appearance publication defined in `M1_BRIDGE.md`, posted through WebView2 after
native origin/security attachment. Its packaged receiver validates the complete schema and may update
only fixed root appearance datasets and CSS custom properties. It exposes no
browser-to-native sender, command, URL, path, HTML, or dynamic property name and
therefore does not widen bridge authority. Windows observation subscribes
before its mandatory initial read; notifications only advance a generation,
and one bounded UI-thread drain reads and applies current state before assigning
the next publication revision. A newer notification is deferred to another UI
turn, so an older callback-thread snapshot cannot win or starve the pump.

Raw `SystemAppearance` remains Windows-owned evidence. The theme consumer turns
that same path into effective-appearance publication by
combining it with the stored override only when deriving native and page
presentation: `system` follows Windows, `light` and `dark` replace the
ordinary color mode, and active high contrast temporarily retains Windows
authority without changing the stored choice. Accent and reduced-motion inputs
remain system-owned. Cosmetic initialization is independently degradable and
never joins document readiness or operational command admission. The host
reads the initial cosmetic snapshot before window creation, uses it for the
opaque background and appearance controller, and then subscribes with
monotonic revision filtering. The page selector starts only after `OPEN`,
serializes replacements, and leaves an unchanged post-uncertainty revision
disabled rather than claiming settlement. Each validated native appearance
publication asks an already-open selector to refresh through the same typed
read. That read carries either null or the exact presentation revision the page
just applied; host composition uses it only to retire the matching replaceable
document post before returning the cosmetic snapshot. A stale or mismatched
revision retires nothing. This lets a healthy new document converge a late
prior-document mutation without widening bridge or cosmetic authority.

GUI Break 1's icon helper is presentation-only and never becomes another bridge
or asset-authority surface. It resolves one exact visual glyph name through a
frozen source-owned `icons.js` registry to fixed inert CSS classes. Those
classes select package-local CSS-mask SVGs and inherit `currentColor`; no view,
payload, command, or returned string can supply markup, a class, URL, path, or
registration. Unknown names and sizes are refused before DOM mutation.

`M1_BRIDGE.md` is the sole normative authority for the immutable production
command mapping, envelope/codec boundary, opaque ids and slots, exact errors,
deadlines/retry and revision identity, drain queue and recovery, visible
sequence, terminal reconciliation, terminal-session release versus explicit
task close, and all BR-G evidence. Implementation placement remains discrete:
`commands.py` owns rows and validators, `bridge.py` owns dispatch security,
`slots.py` owns bounded process-local opaque intent slots, `drain.py` owns
adapter task/event/artifact custody, and only `assets/bridge.js` references
`window.pywebview`. Under the accepted location-admission contract, workflows
own path parsing, probing, and candidate classification; a slot never becomes a
second path-policy authority.

The explicit-`Gap`-only recovery and command-specific `start_plan` revision
decisions are ratified and their named regressions have landed. Numeric holes
alone are not recovery signals. Required ordinary Node probes are unmarked and
non-skippable; probes marked `supplemental_node` may skip without Node. Both use
`NAMISYNC_TEST_NODE` before `PATH`. The required drain gate owns atomic batch
rejection plus clean replay, while the remaining named browser-behavior
witnesses run through the installed production bridge and renderer in real
WebView2.
The frozen v1 SH-G-8/BR-G-42 event-and-transport-custody claim is closed by the
historical evidence below. Independently, the current ordinary deterministic
fixture proves four observations precede tick zero, the exact 60-logical-second
6,000-`Progress`/600-reliable-item shape is lossless and ordered, progress is
monotonic after coalescing by its byte-work high-water, all four terminal
records arrive, and subscriber and adapter queues stay at or below 64. The
separate 260-reliable overflow
regression remains explicitly beyond-envelope and preserves visible
`Gap`/tail/terminal reconciliation. The
standalone installed-wheel WebView2 harness remains useful event and diagnostic
infrastructure. Production progress-only drains now use one fixed,
non-extending 150 ms first-availability deadline capped by the original long
poll; reliable, `Gap`, terminal, recovery, close, and supersession wake
immediately. The first detailed progress value on an idle task may consume the
full interval; receipt and reliable running-state feedback bypass that linger.
Corrected custody
support now includes a path-local retained-state sizer that reports replay,
subscriber, adapter, and identity-deduplicated union graphs without charging
terminal result subtrees to transport. The installed-wheel harness streams
bounded SHA-256-manifested browser samples and producer timings, assembles them
after child exit, and assigns the actual child directly to the Job before
product composition. Its per-PID role/private-byte and thread/handle/topology
series remain diagnostic; `passed` is the event-envelope result and its local
`sh_g_8_acceptance` remains `incomplete-without-custody`, so that artifact is
not the separate custody closure authority. Whole-runtime acceptance remains
explicitly undefined. The frozen
`sh-g-8-transport-v1` calibration-a/holdout-b corpora drive the real built-in
dispatcher replay, subscriber, and adapter deques through
`Dispatcher` -> `NamiSyncService`/`SessionObserver` -> `TaskRegistry`. The
runner proves the quiescent per-task 128/64/64 maximum without `Gap`, ordered
lossless 129-item cleanup, and a terminal path-cut witness that reports result
artifacts separately. It binds three fresh-process artifacts to clean committed
source and instrument authority, an isolated `-I -S` parent, safe-path `-P -S`
children, fresh out-of-tree bytecode caches, hashed active-venv `xxhash`
dependencies, stable qualifier hashes, and an external exact-schema receipt. Its predeclared
headroom rule is now mechanically frozen by a separate ceiling contract; the
runner does not itself decide acceptance, while the independent holdout below
does.
The committed `tests/interfaces/web/sh_g_8_transport_calibration.json` artifact
now records the normative calibration-a union measurements: 1,376,690 bytes /
4,890 objects ordinary and 1,534,946 bytes / 5,499 objects at the exact maximum
no-`Gap` snapshot. The committed
`tests/interfaces/web/sh_g_8_transport_ceiling.json` contract freezes the
1,966,080-byte (1.875 MiB) ceiling. The accepted
`tests/interfaces/web/sh_g_8_transport_holdout.json` artifact records 1,351,794
ordinary and 1,513,014 exact-maximum bytes, respectively 614,286 and 453,066
bytes below the ceiling. Its three fresh runs match the frozen authorities and
pass the no-`Gap`, ordering, 128/64/64, cleanup, and terminal predicates. This
closes the frozen v1 SH-G-8/BR-G-42 event-and-transport-custody claim only.
Terminal result graphs
belong to BR-G-45, not that
custody total. A valid 2026-08-13 run passed its exact event, latency,
no-`Gap`, and clean-shutdown checks and measured a 67,375,104-byte whole-Job
delta, but that value neither passes nor fails realigned SH-G-8 or SH-G-15.
The existing diagnostic command is `.\.venv\Scripts\python.exe tests\bridge_event_benchmark.py --output "$env:TEMP\namisync-bridge-event-benchmark.json"`.
The clean-commit custody calibration reproduction command is
`.\.venv\Scripts\python.exe -I -S tests\bridge_transport_custody.py calibration --output "$env:TEMP\namisync-bridge-transport-custody-calibration.json"`;
the durable artifact was generated from tested commit
`56c50b43dc19090ad33af031891503bfec80599b`. It is a normative calibration
measurement; the separate ceiling contract supplies the byte limit. Acceptance
was then established by three fresh valid holdout-b runs under the exact
authorities, with both ordinary and exact-maximum union measurements below the
ceiling. A separate current-source live guard runs one child, validates its
complete artifact, authenticates the frozen contract, and compares both live
custody shapes directly with that ceiling. It is regression evidence, not a
new acceptance run.

The required v4 representation reruns completed on 2026-08-22. The final clean
installed-wheel event artifact from `7ea8e08666b9079dbb402711f1380c91ae90ef9e`
has SHA-256
`7bb456329fa950fa9c7447bb353590e7902d716233a99c035e58d9467168ab8f` and
passed its event-envelope checks with no `Gap`, monotonic Progress, all four
terminal records, 40 ms p95 / 48 ms maximum sampled Progress delivery, and
3.05 ms p95 / 15 ms maximum sampled reliable-plus-terminal delivery. Its
explicit `sh_g_8_acceptance=incomplete-without-custody` result and undefined
whole-runtime acceptance remain controlling: this was diagnostic/regression
evidence, not current-source Tier-2 timing acceptance. The final clean
current-source custody artifact from the same commit has SHA-256
`a4ba30a99fb3ccc27a20a1fe436ccb8f19ce10e4d7be70572190629abc84ae9c` and
three exact fresh children at 1,378,867 ordinary and 1,536,994 maximum-no-`Gap`
bytes, respectively 587,213 and 429,086 bytes below the frozen ceiling; the
protected one-child guard passed as well. That is Tier-1 drift evidence only,
not a v4 calibration or acceptance run. `M1_BRIDGE.md` owns the exact fixture,
artifact hashes, source/runtime/dependency receipts, queue shapes, and
measurement disposition. No containment command/result is claimed yet.

The deferred-directory spotlight/reducer follow-up was remeasured from clean
commit `32b226e7810c3727a960781108dc15c76d58b570`. Its first installed-wheel
diagnostic preserved event correctness, monotonic Progress, no `Gap`, and all
terminals but failed the diagnostic latency verdict on one 476 ms reliable
maximum; the immediate clean repeat passed at 4 ms p95 / 18 ms maximum reliable
delivery and 41 ms p95 / 48 ms maximum Progress delivery. Both artifacts and
the failed-then-passed disposition are retained in `M1_BRIDGE.md`; neither was
promoted to v4 Tier-2 acceptance. The source-authenticated one-child
custody guard also passed with unchanged ordinary and maximum byte/object
values, so the historical v1 authorities remain unmodified and the new result
remains Tier-1 drift evidence. Its deliberate all-zero `tested_commit` sentinel
does not establish provenance; the current source hash recorded in
`M1_BRIDGE.md` does.

The 2026-07-30 reality run used CPython 3.13.14, pywebview 6.2.1,
pythonnet 3.1.0, Bottle 0.13.4, and WebView2 Runtime 150.0.4078.105. It forced the
`edgechromium` renderer, reached
`Microsoft.Web.WebView2.Core.CoreWebView2`, exercised pythonnet native event
subscription, observed a random loopback asset origin, and confirmed that
bridge handlers receive a Python `str` URL off-thread while also exposing the
canceled-navigation discrepancy above.

The promoted product host now applies that boundary in the exact startup
order. It acquires the fixed instance identity before logging or webview import,
prepares the renderer before service/window construction, validates and if
needed initializes the database pair before command admission, creates one
pending `NativeDocumentState`, and binds its loopback origin once during the
renderer-checked initialized callback. The host snapshots the immutable
production mapping defined in `M1_BRIDGE.md` before exposing the page. Initial
loaded attachment refusal rejects authority, attempts public destruction once,
and requests one owner-bound native close if the public call throws or returns
without closing; pre-native initialization failure does not call destroy.
Neither close request guarantees closure. After the GUI loop returns, one
finalizer closes any constructed service, then releases logging, app-path
leases, and the mutex only after complete quiescence, preserving the initiating
startup diagnosis. Every failure caught after logging configuration
records one typed `startup.failed` traceback before that finalizer; diagnostic
failure cannot replace the native report or process exit status.
Native `loaded` starts a fixed five-second document-readiness deadline rather
than opening commands. The packaged module installs the neutral readiness
receiver before the appearance receiver and shell, acknowledges the current
generation through `dispatch`, waits for the host challenge, and echoes the
identical nonce. It marks the bridge operational and shows `Ready` only after a
truthful `{"acknowledged":true}`. False or transport uncertainty permits
exactly one identical-payload retry. Appearance continues to apply
independently and may truthfully degrade. A true reload or same-page pywebview
reinjection repeats the bilateral handshake. Initial refusal uses the
startup-only teardown. After a previously open generation, a readiness refusal
that wins while the host remains open records the diagnosis before entering the
ordinary bounded service-close state machine, so active work is never bypassed
by direct destruction. A close already in flight retains ownership and the
later refusal cannot replace it.
Clean-wheel headed gates exercise this composition through the real pinned
WebView2/pythonnet stack, including packaged-page popup composition, canceled
navigation, guard-attachment failure, runtime refusal, activation, and the
visible coordinated-database refusal.

Normal window close is a separate host-owned state machine. An admission
condition around `BridgeDispatcher.dispatch` rejects new calls and waits a
bounded interval for admitted calls without adding another JavaScript-facing
method. The synchronous WinForms callback only claims one worker and vetoes;
that worker rejects new dispatch, marks adapter delivery closed and wakes its
waiters, waits for admitted handlers, then invokes service close. Window-owned
appearance remains subscribed during every
retryable failure. Only a complete shutdown closes appearance exactly once and
permits programmatic destroy. Incomplete and exceptional
attempts retain the page status and one owned native Retry/Cancel prompt; Retry
alone starts another attempt, and the finalizer does not close an
already-complete service twice.
The loaded callback also binds the current fixed status element before any
asynchronous close render. Repeated loads replace that cached presentation
target, so a late worker never queries a destroyed document; missing/write
failure is logged without changing the close phase or service result.

## Common Adapter Contract

- Bound each complete externally supplied request at ingress. `M1_BRIDGE.md`
  exclusively defines the desktop ceiling; a future REST, IPC, or other adapter
  must impose an equal-or-stricter whole-request limit before constructing
  internal presentation values.
- Enforce the bridge/defense numeric-domain contract before persistence or view
  construction; do not reinterpret opaque identity as arithmetic.
- Validate syntax/presence early and report actionable path/input errors; domain
  validation remains in workflow/preflight.
- Submit through dispatcher/registry rather than starting ad hoc workers that
  call modules directly.
- Read current session records and observe through the service's sink API.
- Treat progress as a replaceable snapshot. Handle bounded state/item/terminal
  delivery, including `Gap`, durable reliable-event page catch-up through a
  fixed watermark, and resubscription for an ejected/late ordinary subscriber;
  history has timeout-bounded admission delivery and an atomic finalization
  ownership cutoff that keeps live and retained audit axes equal.
- Present refusal, cancellation, partial failure, recording-behind, history
  failure, integrity mismatch, and verification-incomplete as distinct states.
- Keep plan, inventory, and history presentation models orthogonal.
- Commit only after the plan session terminates. Validate the exact core
  commitment from [M1_BRIDGE.md](M1_BRIDGE.md); execution exposes no field that
  can resupply a frozen choice. Never expose an “execute anyway” path around
  commitment or fresh preflight. Reviewed preflight notices describe the
  initial selection; after edits they remain context, while execution freshly
  preflights the committed set.
- Runtime thread/ownership guards raise real exceptions, not `assert`.

## Shared Actions

An interface action has one source of truth for label, enablement, shortcut,
scope, confirmation, and dispatch. Menus, buttons, context menus, and commands
adapt that action rather than duplicating rules. Enablement is derived from
typed state and selected scope; hidden/filtered selection is disclosed.

Presentation logic that selects a row, computes scope, or builds a result model
is testable without entering a modal event loop.

## Session And Worker Boundary

Dispatcher remains each admitted session's custody and control truth; the
application lifecycle is the sole owner of domain-effect receipts, association,
compensation, and settlement. The adapter serializes only presentation and
transport delivery without owning volume locks or rewriting dispatcher/history
truth. Publication faults follow the bridge protocol, provisional queue state
is discarded locally, and queued events cannot repopulate it. Toolkit delivery
is task/session-checked and marshaled to the UI thread; terminal delivery is a
fact supplied to high-level settlement, not authority for adapter-side observer
release or session cleanup.

## Security And Data Isolation

Explicit database overrides reach both ledger and history. Tests never default
to real `%LOCALAPPDATA%` databases. Paths and annotations are treated as data;
no shell interpolation, HTML injection, or spreadsheet formula execution is
introduced by rendering/export.

Read-only commands/views may coexist with active writers under WAL. Mutating
interfaces use the same dispatcher and physical-volume custody; GUI single
instance is a presentation-instance rule, not a global ban on safe CLI work.

## Future Remote API

A future remote/non-bridge API adapter exposes versioned request/result/event
schemas, authentication, local binding by default, explicit replay gaps, and no
direct module endpoints. It is not scaffolded until a concrete client exists;
the core event schema version is the provisioning seam.

## Expectations

- Dispatcher supplies generic state/control/events.
- Workflow registry/composition root supplies typed activity adapters.
- Core reason/outcome schemas are stable and presentation-neutral.
- Repositories expose read models only through workflows/application services;
  interfaces do not issue SQL.
- UI and CLI do not infer domain success from zero bytes or green styling.

`OperationResult.recording` and `.audit` expose independent ledger/history
durability, while `Disposition.RAN|UNRUN` distinguishes discarded/refused work
from a zero-byte activity that actually ran. Interfaces render these typed axes
without parsing diagnostics or overloading filesystem status.

## PoC Hardening

The layer contract prevents dead real CLI argv, real-user test database writes,
plan-wide blocked gating, stale worker GC/release, premature thread destruction,
per-chunk UI floods, uncancelable import close, wrong-location fallback,
plan/inventory state conflation, misleading partial/refused completion, modal
test hangs, duplicated action wiring, and `assert`-only thread guards.
