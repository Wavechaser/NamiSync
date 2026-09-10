# Interfaces Layer

This document owns the implemented CLI and desktop adapters, service/task lifecycle, and desktop host/package rules. It does not define domain policy: workflows own domain admission and execution, the dispatcher owns generic session custody, and repositories remain behind application services.

`BRIDGE.md` owns external desktop protocol, transport, retry/recovery, and its exact evidence. `PRESENTATION.md` owns tree/view/search/sort/selection behavior and visual scale evidence. The frozen v1 event-and-transport custody result is scoped to its bridge evidence and does not establish whole-runtime containment. The former BR-G-45 aggregate terminal-artifact model is retired. SH-G-15 remains an open, scoped release criterion defined below.

The active service and CLI support sync, inventory, baseline, verify and rebaseline. The desktop exposes the bounded host/transport foundation and process-live blank task pages with creation, navigation, reconstruction, and explicit close. Frozen Setup, plan/execution review, inventory projections, manual post-copy verification, and the history/settings pages remain accepted but unrealized outcomes. Their delivery register is [M1_PLAN.md](M1_PLAN.md).


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
new artifact. In the accepted, unrealized desktop flow, changed Setup
or explicit Plan again creates a new task, while the old plan slot stays
immutable. Plan again asks the backend to resolve the retained plan's reviewed
volume identities into fresh Setup slots; it never submits the old display path
or copies selection state. Only a failed admission restores `reviewing` today;
a preflight refusal after successful admission leaves selection committed. M1
does not add terminal subset retry or reopen that committed selection. Its
recovery is explicit Plan again, fresh scans, and new review/authorization. This
also accounts for source or target files removed while freeing disk space;
neither an old selection digest nor a new free-space reading certifies an
unchanged filesystem. The direct-service replacement behavior above is not a
desktop recovery command.
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

Exact wire and scalar encoding live in [BRIDGE](BRIDGE.md). Implemented lifecycle is described here; [DEFENSE](DEFENSE.md) owns quantitative authority and boundary policy.

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
[Bridge sorting contract](PRESENTATION.md#search-filters-sorting-and-follow).

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

`TaskLifecyclePort` exposes lifecycle-only shell create/close, task-bound start
and cancellation, exact task/session reobservation, terminal-session release,
and task close. A shell owns only its task id; it creates no request, plan,
session, observer, or domain result. The application mints the task id and
supplies it to the factory before publication or dispatcher admission. A
factory may create provisional adapter state; its own call frame discards that
state on failure, and no application or service rollback refers back into the
adapter. The web registry enumerates only successfully published tasks.

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

`interfaces/web/_exception_graph.py` intentionally keeps the small
exception-retirement operation adapter-local because the interface import law
bars core and the drain-specific contract bars lifecycle owners. Do not relax
either boundary merely to deduplicate it; reconsider a neutral owner only if
another interface consumer needs the operation.

The application admits at most 48 active desktop task effects before invoking a
delivery factory or lower application work. Independently, the adapter keeps at
most 48 successful/in-flight start-response entries, retiring successful entries
with their tasks, and one shared population of 48 shell/session close-response
tombstones with least-recently-used eviction. These are exact count bounds and
make no retained-byte or whole-runtime memory claim. Terminal-session release
closes observer and Dispatcher custody while retaining the task and its actual
terminal headline; only explicit task close retires the card and remaining
task/plan ownership. Busy close is an exact task/session cancellation request,
then a close after delivered settlement. A failed close leaves the task
available for the same close recovery path.

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

## Desktop host, package, and release criteria

### Launch and installation

NamiSync has one GUI implementation and two correctly classified Windows entry-point families. `nami-sync` and `python -m namisync` are console entry points; without a subcommand they show usage and direct the user to `nami-sync-gui`. `nami-sync-gui` is a GUI entry point and does not retain a console window. `interfaces/launcher.py` owns `main(argv=None)` and `gui_main(argv=None)`; CLI work must not import pywebview. The GUI launcher completes path and logging setup before importing the web host.

GUI arguments are closed: no arguments or one absolute local `--data-dir PATH` (including equals spelling). Unknown/positional/repeated/missing arguments and relative or non-local paths fail before directory creation, mutex acquisition, logging, or pywebview import. A dependency-free Win32 `MessageBoxW` reporter with caption `NamiSync - Startup Error` shows actionable startup failures when no console exists. Logging records failures once available; a second-instance activation is the settled non-error case.

The supported desktop stack is CPython 3.13 on Windows 11 x64, `pywebview==6.2.1`, `pythonnet==3.1.0` on Windows, and Bottle 0.13.4 or later. NamiSync supports the tested pythonnet netfx route and refuses a conflicting `PYTHONNET_RUNTIME`. A change affecting pywebview, pythonnet, clr_loader, or return transport reruns the relevant native reality and hostile-text checks.

The window's native return adapter consumes a one-shot marker from the bridge's
existing document generation after command processing. It contains obsolete
pywebview JavaScript callback failures across reload without canceling or
repeating command effects. Stable-generation JavaScript failures and non-JS
failures remain visible; handler custody still waits for true worker exit.
[BRIDGE.md](BRIDGE.md#current-envelopes-and-admission) owns the precise containment
boundary and its race limitation. It also protects the small admission return
for asynchronous commands; asynchronous completion does not remove that race.

The native bridge separates admission from completion only for `create_task`,
`start_plan`, `release_terminal_session` and `close_task`. CommandSpec owns that
classification; custom commands and ordinary Python dispatch retain synchronous
results. The host binds the dispatcher to its existing DocumentChannel after
construction. Reload retires old completion delivery before a new readiness
exchange, while admitted handlers continue through their existing task/session
owners. Close rejects new admission, wakes drain waiters and retires completion
delivery before waiting for both native and command workers. A bounded wait
failure leaves shutdown retryable and cannot close the service under live work.
BRIDGE owns the exact delivery phases, bounds and recovery contract.

One immutable `AppPaths` resolves all GUI artifacts. Production uses `%LOCALAPPDATA%\NamiSync`; tests and development inject an isolated root, including for every headed test. The root contains ledger/history databases, settings and UI state, logs, and WebView2 storage. The data-dir override is application composition input only: it is never browser supplied or persisted as session authority. Pywebview uses private mode and the explicit root-local WebView2 storage path.

`namisync/version.py` is dependency-free and owns the single product/distribution `VERSION`; package metadata, runtime, About, and logging agree on it. `NICKNAME` may be human-facing but is never compatibility, schema, filename, mutex, or protocol authority. License declarations travel with package metadata; third-party notices, corresponding-source directions, and the visible distribution license bundle are release work.

### Logging and host startup

GUI logging is standard-library-only and configured before pywebview import. It eagerly opens `logs/namisync.log` with an UTF-8 `RotatingFileHandler`, 5 MiB maximum, five backups, and `backslashreplace`. The one shared handler serves the non-propagating `namisync` and `pywebview` loggers at INFO and neither configures nor mutates the root logger. It is idempotent, installs one wrapper each for `sys.excepthook` and `threading.excepthook`, and uses UTC millisecond records with level, PID, thread, logger, and message. It records startup/runtime version facts and typed stable diagnostics without formatting raw bridge bodies, returned domain objects, settings, filenames, or paths. Tracebacks and external errors can still contain paths, so logs require review before sharing. Log failure never changes operational, ledger, history, or shutdown truth; normal finalization logs then calls `logging.shutdown()`.

The host acquires fixed instance identity before logging or webview import, prepares the renderer before service/window composition, validates or initializes the database pair before command admission, binds its loopback origin once after renderer-checked initialization, and snapshots the bridge mapping before exposing the page. Startup refusal performs only the applicable owner-bound teardown and retains the initiating diagnosis; every post-logging failure records typed `startup.failed` before final cleanup.

A loaded document has a fixed five-second readiness deadline. The packaged readiness receiver starts before appearance/shell, acknowledges its current generation through dispatch, waits for a host challenge, and echoes the identical nonce. Commands and retained drains remain unavailable until the truthful acknowledgement. Transport uncertainty permits one identical-payload retry. Reload/reinjection repeats the handshake. Appearance may degrade independently of readiness and command admission.

Window close is host-owned. It rejects new dispatch while waiting boundedly for admitted calls, closes adapter delivery and wakes waiters, then invokes service close. Incomplete or exceptional closure leaves the window open with one owned Retry/Cancel interaction; only a completed shutdown closes appearance and permits programmatic destroy. A repeated load replaces the cached status target, so a late worker never queries a destroyed document.

### Package and frontend placement

The frontend is plain local ES modules: no Node, npm, framework, bundler, transpiler, source map, inline script, or inline event handler. The CSP meta element is first in `head`; every import names a local file. Production package resources provide the page. A Python-construction-only absolute local index override exists for headed tests and is unavailable from GUI arguments, the bridge, or page data.

Only `assets/bridge.js` may reference `window.pywebview`; the host exposes only the function-table dispatch entry. Presentation assets and local icon provenance follow the fixed-registry rules in `AGENTS.md`. `PRESENTATION.md` owns tree/window behavior and focused scale; `DESKTOP_UI.md` owns visual acceptance; `BRIDGE.md` owns wire protocol and transport rules.

### SH-G release criteria

| Gate | Active criterion and verification |
| --- | --- |
| SH-G-1 | From a built wheel installed in a clean venv, `nami-sync` with no subcommand prints usage naming `nami-sync-gui` and keeps its usage status; explicit CLI work loads no `webview` module; `python -m namisync` behaves the same; and generated `nami-sync-gui` declares the Windows GUI subsystem. In-process launcher calls or source-tree assertions do not close this gate. |
| SH-G-2 | With an injected isolated root, ledger, history, settings, UI state, log, and WebView2 artifacts all resolve below it. A headed data-dir run leaves the real per-user root unchanged and a relative data-dir fails before directory creation. A static scan proves only `paths.py` reads `LOCALAPPDATA` or builds the NamiSync GUI path; the workflow resolver remains the separate CLI authority. |
| SH-G-3 | Repeated configuration yields one shared handler, one wrapper for each exception hook, no root mutation, and the declared level/propagation policy. A successful child GUI path eagerly emits parseable UTC records, pywebview records, startup version facts, and selected native renderer identity without console output; rollover, Unicode/surrogate handling, thread/process exception logging/delegation, and hostile-body/path non-retention are each exercised with emitted records. Configuration-only or test-process logging is insufficient. |
| SH-G-4 | `namisync.version.VERSION`, installed distribution metadata, and the startup log agree. A fresh subprocess importing `namisync.version` loads no other NamiSync module. Schema or protocol versions are not additional witnesses. |
| SH-G-5 | Fault-injected mismatched ledger/history markers in an isolated root show the coordinated manual-reset direction in the real visible GUI, leave database files byte-identical, and do not silently exit. A parent locates and dismisses the production Win32 dialog by stable caption and observes child exit. A log-only, mocked, or service-only refusal is insufficient. |
| SH-G-6 | A built wheel contains each packaged asset; `importlib.resources` resolves `index.html` from the installed wheel in a clean venv; and headed smoke loads that resolved page. Source-tree resolution is insufficient. |
| SH-G-7 | The exact installed asset set is scanned: only `bridge.js` references `window.pywebview`; `index.html` has one first-head CSP meta matching the bridge policy; there is no inline script/event attribute; and shared row-height declarations agree. Installed headed evidence proves the accessible empty shell, 200% reflow/forced-colors focus, virtualized navigation/disposal, stale-generation refusal, hostile layout-marker rendering with ordinary Unicode preservation, bounded DOM rows, and production manifest agreement across Python, browser child, and page. Hand-maintained asset lists, test-only trees, gallery-only evidence, or copied renderer rows are insufficient. Presentation-specific visual details remain in `PRESENTATION.md`. |
| SH-G-8 | `BRIDGE.md` owns the frozen v1 attach-before-start, ordered reliable delivery, progress linger, Gap/recovery, queue-custody, calibration, and holdout evidence. It proves only event-and-transport custody, not terminal-result retention or whole-runtime containment. |
| SH-G-9 | Deferred with the history page. When activated, a live cursor ahead of durability must render the committed prefix, terminate on an empty terminal page without retry looping, and obtain later repair only through a fresh read. |
| SH-G-10 | Production always constructs the fixed `DesktopInstanceIdentity` for `Local\\NamiSync.Desktop` and title `NamiSync`; AppPaths/data-dir cannot alter it. Production launches collide on that mutex, injected distinct test identities coexist, window and activator titles come from the same identity, and no argv/environment/bridge/page input overrides its namespace. |
| SH-G-11–14 | `PRESENTATION.md` and the visual owner retain the exact token, material/fallback, motion, fixed-local-icon, and installed-wheel evidence criteria. |
| SH-G-15 | Open scoped release acceptance. Before measuring, declare the installed build, runtime/hardware profile, observed process scope, finite cold-start/repeated/long workloads, repetitions/durations, warm-up/quiescence, fresh-process count, statistics, separate resource predicates, budgets, and validator. Measure stable host and relevant runtime/renderer-child identities; preserve raw observations and dispersion without materially contaminating the product. Require absolute cold-start peak and settled use plus retained-growth and trend checks. An incomplete workload or missing observation cannot pass. Scoped Tier-2 acceptance applies only to named profiles/workloads; relevant source, dependency, or runtime changes rerun affected profiles against unchanged budgets unless explicitly revised. Tier-3 rules govern calibration-derived ceilings or invalidated authority. No budgets or acceptance artifacts exist yet. This does not revive BR-G-45 or weaken runtime-enforced request/population bounds. |

## Common Adapter Contract

- Bound each complete externally supplied request at ingress. `BRIDGE.md`
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
  commitment defined in [core execution](../namisync/core/execution.py); execution exposes no field that
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
