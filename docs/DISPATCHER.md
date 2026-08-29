# Dispatcher Module

Status: M0 implemented and acceptance-tested. M1 Stage 4's generic
registration-owned canceled-settlement seam for already-started opaque work is
implemented. Stage 6 Slice 3 adds the domain-blind transactional admission
`attach` seam used by desktop task observation; the dispatcher remains
domain-blind. M2 durable queue ownership, SQLite session persistence, and
startup reconciliation remain deferred.

Terminal continuation scrubbing and exact-v5 event admission are active. The
remaining Stage 6 second-half desktop task target is not active yet. It reuses
the existing `attach` seam for every desktop-created session and lets an
interface-owned process-live task serially bind those sessions. No task id,
task revision, retained presentation artifact, or bridge retention policy enters
dispatcher; any implementation of that target must preserve this boundary.

## Purpose

Dispatcher admits, schedules, controls, and observes generic sessions. It knows
session ids, states, required resources, opaque workflow kind/request/result
payloads, and event delivery classes. It does not know what sync, verify,
baseline, import, or ingest means and never imports modules, database, or
workflows.

## Public Contract

```python
submit(kind, request, *, attach=None) -> SessionId
pause(session_id) -> ControlResult
resume(session_id) -> ControlResult
cancel(session_id) -> ControlResult
subscribe(session_id, from_seq=None) -> EventStream
get(session_id) -> SessionRecord
list(query=None) -> Sequence[SessionRecord]
close(session_id) -> None
shutdown(timeout) -> ShutdownResult
```

An injected registry maps opaque kind to a generic callable/capability adapter.
`prepare(request)` returns opaque bytes plus a set of generic `ResourceId`
values. `open(payload)` belongs to the adapter and returns a fresh invocation
with `run(ctx)` and `snapshot()` methods. The dispatcher calls those methods but
never decodes, reflects over, or otherwise interprets the payload. Reopening the
invocation on every resume is the generic seam through which the owning workflow
runs its fresh guard.

The optional domain-blind admission `attach` callback receives only a newly
allocated session id and preopened `EventStream`, and returns an idempotent
rollback callback after adopting the stream. The record, hub, and store row are
still unpublished and unschedulable. A caller whose attachment can acquire an
owner before raising supplies an exact `AdmissionAttachment`: Dispatcher rejects
subclasses, snapshots its attach and rollback callbacks before workflow
preparation, and transfers that pre-registered rollback only after attachment
invocation begins. A successful attachment must return that exact callback.
Dispatcher emits `PENDING` to the adopted
stream, then atomically publishes its maps/pending entry and notifies the
scheduler. Every exception through `PENDING` emission and publication takes
the same cleanup path. After adoption, dispatcher invokes the returned rollback
first so it signals, closes, joins, and identity-removes that observation, then
closes its remaining stream/hub ownership and drops the store row. Cleanup
failure is retained as non-schedulable cleanup-pending ownership and makes
shutdown incomplete without replacing the initiating exception. A nonblocking
claim serializes admission's cleanup-liability interval; a competing or
recursive admission receives one fixed `SessionCleanupPending` refusal before
preparation or allocation. At most one failed unpublished owner can remain.
Only its separately tracked daemon worker calls rollback, stream, hub, or store
cleanup, with no dispatcher condition or blocking gate held. The initiating
submission may join that exact worker for at most the audit timeout. A later
admission can start or reuse its retry worker but still returns the fixed
refusal; admission resumes only on a later call after exact worker retirement.
Shutdown likewise only starts or reuses and deadline-joins the exact worker; it
never runs injected cleanup inline, never duplicates a live attempt, and
reports the unpublished session id while cleanup remains incomplete. A cleanup
worker invoking shutdown cannot join itself. No task identity or interface
policy enters dispatcher.

The desktop service pre-registers one retryable composite rollback from the exact task
reservation, optional runtime-detail owner, and `SessionObserver` adoption. It
checks the observer's exact `(session_id, sink)` identity after every attempted
retirement. If that owner survives, the callback raises a fixed cleanup-pending
failure and leaves the task reservation charged, so this Dispatcher worker—not
an interface-local retry queue—remains the sole retry authority. Detail cleanup
may complete independently; task detachment occurs only after observer and
detail owners are both absent. The initiating submit exception remains the
public failure throughout.

The desktop task owner-claim, binding, lease, epoch, and release protocol is an
interface obligation specified by [M1_BRIDGE.md](M1_BRIDGE.md); it uses the
existing transactional `attach` seam and does not expand dispatcher policy.
Dispatcher retains the full opaque `OperationResult` until explicit session
close, but neither builds the bridge summary nor serializes result items to
JavaScript.

One optional registration callback,
`settle_canceled(payload, disposition) -> OperationResult`, handles cancellation
of work that already has a start time but will not re-enter its normal
invocation (paused work and resume→pending cancellation races). Dispatcher
passes the opaque payload and generic disposition only, validates that the
returned result projects to lifecycle `CANCELED`, then follows the ordinary
audit/Terminal/custody path. Registrations without the callback retain the
generic canceled result. A callback failure is an explicit adapter failure and
terminals `FAILED`; it is never masked as clean cancellation.

`close()` is distinct from cancellation: it accepts only an already-terminal
record and first waits for that session's exact worker thread to exit, outside
both dispatcher locks. Worker retirement and subsequent publication/audit
cleanup share one bounded deadline. A worker cannot close its own session;
self-close and a retirement timeout are explicit retryable refusals that leave
the session and its subscriptions intact. Successful close therefore includes
worker-frame retirement, not merely terminal publication. It then blocks new
subscriptions and waits for audit/subscriber cleanup before dropping the
session-store row or any in-memory ownership. Hub cleanup reports
whether it completed, timed out before acquiring the hub publication gate, or
closed subscriptions but still has audit cleanup pending. A pre-gate timeout
changes no hub state, removes the temporary close claim, and allows subscription
or a later close retry. An attachment racing that tentative explicit close
waits for its bounded outcome; it does not receive a cleanup-pending error
unless the close crosses the irreversible boundary. Once subscriptions are
closed, `close()` raises a `TimeoutError` that identifies cleanup as pending
and retains the record, hub, controls, publication lock, and close claim for a
safe caller-owned retry. A store-drop failure retains that same irreversible
cleanup state. `shutdown()` stops admission, attempts cancellation first for
every session whose publication and hub gates
are immediately available, then spends only its remaining shared deadline on
deferred gates and cleanup. Shutdown reserves the hub before persisting
`CANCELING`, then offers the matching audit event without waiting on queue
capacity; expiry therefore leaves lifecycle state unchanged and retryable
instead of separating it from its reliable event. It returns explicit
`complete`, `unfinished`, and `custody_released` facts. Explicit close and
shutdown serialize per-session hub cleanup through that publication lock.

## State And Runner Ownership

Dispatcher enforces core's one legal transition table. The generic core session
runner owns start/end timestamps, exception containment, pause/cancel
resolution, and exactly-one terminal emission. Modules return typed opaque
results and emit only nonterminal events through `RunContext`; dispatcher owns
custody around the runner and releases it in every exit path.

Failures raised before invocation entry by lock acquisition, continuation open,
or retained-payload cancellation settlement are projected to fixed terminal or
control truth before the core runner is called. Dispatcher clears the caught
exception's traceback, cause, and context after bounded diagnostic projection,
so the runner closure and terminal store cannot retain collaborator frames or
attached private graphs. A failing diagnostic renderer omits the detail rather
than retaining either failure. Process-fatal `BaseException` propagation and
worker retry behavior remain unchanged.

Each process-local runner attempt has a monotonically increasing private
generation key. A session has at most one current generation; every resource
reservation and acquired lease is owned by that exact key, and state/result/
payload callbacks reject stale keys. Generations never enter public records,
payloads, stores, or databases. This keeps the public lifecycle unchanged while
preventing a retiring pause/cancel attempt from settling twice or releasing a
resumed successor's custody.

Pause is accepted only when the registered kind declares a continuation:
execution in M0 and verify/baseline item-list sessions in M1. Scan and plan
refuse pause without changing state and remain cancelable. An
accepted pause raises `PauseRequested`, unwinds after workflow continuation
state is retained, and reports `PAUSED` only after custody is released. The
domain transition remains authoritative, but worker settlement and live
`PAUSED` event publication wait for a queued audit-flush barrier. Direct
`get()`/`list()` polling may briefly see the domain state first; a failed or
timed-out barrier degrades audit without rolling back `PAUSED` or retaining
custody. Resume re-enters admission at the back of every required volume queue,
never preempts a running session, and starts with the workflow's fresh guard.
`PENDING` may therefore coexist briefly with its prior generation while that
worker finishes audit publication and retirement; the scheduler waits for the
current-generation handoff instead of launching an overlapping successor.
Cancel requests are cooperative but terminal cleanup/release is unconditional.

Execution may deliberately remain `PAUSING` while one durable retry operation
settles from process-local staged state. That module-owned drain does not alter
the dispatcher contract: `PAUSED` still appears only after unwind and custody
release, cancellation still preempts it, and a terminal policy `Stop` may win
the race and take `PAUSING` directly to `FAILED` instead of creating an empty
paused continuation.

M0 preserves the adapter's opaque continuation by calling `snapshot()` after a
pause unwind and before releasing custody or publishing `PAUSED`. This includes
a pause observed at the runner's entry checkpoint before `invocation.run()`;
the admitted invocation still establishes and serializes its resumable
continuation before the dispatcher reports `PAUSED`. Reliable item outcomes are
accumulated by session across attempts, so a pause followed by a later cancel or
failure retains outcomes earned before the pause without asking the workflow to
emit them twice. If cancel reaches a resumed attempt's RUNNING checkpoint before
`invocation.run()`, dispatcher uses the registration's retained-payload
cancellation settlement before publishing the terminal; it cannot substitute a
generic canceled result that strands workflow custody.

`SessionRecord.payload: bytes | None` is process-local opaque continuation
state only while nonterminal. Every edge into `COMPLETED`, `FAILED`, `CANCELED`,
or `REFUSED` atomically clears the current live record's payload before
publishing the terminal state; the state-before-result settlement record and
the later record with its result are both payload-free. Dispatcher does not
inspect or decode the bytes. It may pass them to a registered cancellation
settler before the transition. Ordinary return/failure, cooperative cancel,
queued discard, workflow refusal, paused cancellation, and resume-to-pending
cancellation all retain this live-record invariant. Separately, admission and
every later store write project metadata without any payload field. A store
that accepts one of these values and rejects an update can retain stale
metadata, not that session's continuation. This is not a claim that all earlier
Python references have been erased.

## Admission And Volume Scheduling

Required local physical-volume ids are sorted deterministically before locks to
prevent deadlock. Sessions with disjoint required volumes may run concurrently;
contenders queue. Planning sessions may release locks when complete; execution
reacquires and revalidates volumes.

Scheduler selection installs the current generation, its worker registration,
and all reservations atomically before removing the pending entry or starting
the thread. The selection loop releases its temporary record reference before
launching or waiting, so an idle scheduler cannot retain an earlier payload
after the session closes. `CANCELING` never creates a second worker while an
acquisition or pause generation is current. Worker retirement identity-checks
again under the session publication lock and enqueues any surviving
PENDING/CANCELING handoff.
That worker then marks its exact attempt as retiring; the current-generation
fence and thread ownership remain until the thread is no longer alive. The
The scheduler reaps only started, marked attempts and uses a short bounded wait
only while retirement is pending. A registered thread whose `start()` call is
still unresolved is never mistaken for a finished attempt; a start call that
has returned by raising with no thread identity is instead settled and removed
synchronously as described below. This includes the remaining worker and
handoff frames and a still-running thread exception hook. Shutdown reports a
still-live retiring worker as unfinished even when its terminal result is
already visible. Core `BaseException` propagation is unchanged; an external
exception hook that saves an exception after returning remains a separate
caller-owned reference, not a dispatcher retirement guarantee.

If `Thread.start()` raises before a session worker receives an OS thread
identity, no workflow invocation exists. Dispatcher retires the raw start
failure before entering audit/settlement, publishes one fixed `FAILED + UNRUN`
result through the ordinary state/result/Terminal path, releases the exact
reservation, removes the never-started attempt synchronously, and continues
scheduling. A cancel already accepted while `start()` was blocked instead uses
ordinary cancellation settlement; a resumed session therefore preserves
`RAN`. If `start()` raised after assigning an identity, that real thread keeps
ownership through exit and the scheduler does not manufacture another result.
Public close waits for either form's exact retirement. The scheduler loop drops
its launch reference before waiting, so neither a never-started `Thread` target
nor a completed attempt becomes an idle owner.

Cross-process physical-volume exclusion is required before any M0 mutation,
using a named OS mutex or lock file keyed deterministically by volume serial
with abandoned-holder recovery proven. This is distinct from M2 durable queue
ownership. Unsupported or ambiguous volumes are refused, not scheduled
optimistically. Network-share coordination remains unavailable and mutating
sessions on such roots are refused unless a separate safe guard exists.

The M0 provider uses sorted, deterministically named Windows global mutexes
derived from the resource namespace and key. `WAIT_ABANDONED` is successful
acquisition: Windows has already released the killed owner's custody, and the
new owner must release the mutex normally. Acquisition polls cooperatively so a
queued session can still be canceled. The portable in-process provider exists
for non-Windows tests only and is not a substitute for Windows mutation safety.

Custody has one owner: dispatcher/session runner. Executor never releases locks.
Every terminal, pause-drain, admission failure, workflow exception, observer
failure, and orderly teardown path releases exactly the acquired set.
Lease release occurs on the same worker thread that acquired it; only that
generation's lease and still-owned reservations are removed. A stale cleanup is
idempotent and cannot touch successor ownership.

## Events And Subscription

Dispatcher assigns envelope timestamp/schema/sequence and fans out events.
Progress is lossy/coalescible. History is the distinguished admission-time
reliable subscriber: its bounded buffer backpressures only at a safe checkpoint
boundary and only until an injected generous timeout. Failure/timeout degrades
the session's `audit` status and stops blocking. Any other reliable subscriber
whose bounded queue overruns is ejected and first receives
`Gap(first_missed_seq)`. Late subscribers receive current state plus a bounded
tail/detectable gap—not a false promise of full replay. When the retained replay
is longer than one subscriber's bound, the truncation itself is what creates
that gap, so the leading `Gap` occupies a slot inside the bound: a new stream
never starts with more buffered envelopes than its capacity.

Core event v5 is active under the coordinated cutover defined by
[M1_BRIDGE.md](M1_BRIDGE.md). Dispatcher accepts only that exact event version;
it does not version-dispatch a mixed live stream. The core projector
validates, deeply copies, and size-checks one immutable emitter-owned snapshot
before sequence, replay, history, or subscriber publication. All consumers see
that same snapshot, and every schema-valid queue head remains drainable under
the independent bridge response bound. Exact event fields, scalar domains,
path/detail limits, omission witnesses, and byte ceilings remain centralized in
the bridge and defense authorities.

That full initial buffer is deliberate for now. No finite number of reserved
slots is a contract-derived burst tolerance: a workflow can emit an arbitrarily
long reliable run before an ordinary sink drains once, so one spare slot is
only a one-event courtesy and a larger constant merely moves the same boundary.
With the production 128-envelope replay and 64-envelope subscriber capacities,
an immediate later ejection is visible, and resubscription from
`first_missed_seq` can replay the dropped tail; its cost is duplicate work and a
stuttering consumer, not silent data loss. NamiSync therefore keeps the full
replay tail until UI/load evidence establishes a useful reserve. A consumer
that requires guaranteed continuity needs a readiness handshake or must attach
before workflow start; a magic headroom constant cannot provide that guarantee.

A per-session publication gate spans each persisted lifecycle transition and
its matching reliable `StateChanged`. Later transitions cannot publish first or
make the hub's current-state replay regress, while unrelated sessions remain
independent. Dispatcher also serializes hub subscription registration with
terminal `close()` and shutdown cleanup: if subscribe wins, cleanup shuts that
stream; once irreversible cleanup claims the session, subscribe raises typed
`SessionCleanupPending`, stating that terminal settlement is complete and only
cleanup remains. A pre-publication timeout releases that claim because no hub
state changed. A closed session cannot retain a newly orphaned stream. Retry is
owned by the caller or orderly shutdown for hub/audit cleanup and by the caller
for a failed store drop; dispatcher runs no background reaper.

An ordinary `EventStream.close()` is an immediate unsubscribe as well as a
reader wakeup. The stream invokes its hub-removal callback once, outside the
stream condition, so explicit interface unsubscribe does not leave closed
subscriber objects retained until a later emit or session shutdown. Hub
shutdown spends one deadline acquiring that lock and closing audit, clears both
replay and its subscriber set while publication is excluded, and closes the
detached streams before observer cleanup; ejected streams remain removed by the
emitting path.

History attaches at admission before workflow events. Subscriber exceptions and
timeouts are isolated and surfaced through `OperationResult.audit`; they do not
rewrite filesystem or ledger truth. Dispatcher must not substitute an unbounded
queue or silent loss. The audit pump starts one monotonic flush deadline when
the observer receives the first event in a window. Continuous delivery does not
postpone that deadline; an idle queue wakes at the same deadline and calls the
observer's idempotent `flush()`. Production supplies the history window policy's
one-second age as the interval. A clean nonterminal stop forces one last flush,
while a failed/timed-out flush marks the reliable prefix broken, stops accepting
later audit events, and never finalizes a noncontiguous tail. Before terminal
fanout, the runner drains history and requests finalization through an atomic
ownership latch. A caller that wins the production cutoff settles degraded,
and any row the late pump commits carries that same axis. A pump that wins
makes the caller wait for its actual outcome:
commit success settles OK, while failure settles degraded with no
contradictory row. The immutable Terminal is then sent to ordinary subscribers,
never used as history's own finalization input.

Terminal settlement therefore has one intentional transient for direct record
pollers: dispatcher first persists/emits the terminal `StateChanged` with
`SessionRecord.result is None`, finalizes the audit axis, persists the final
result, and only then emits `Terminal`. A consumer that observes terminal state
without a result must treat it as settlement-in-progress and wait for the result
or reliable `Terminal`; it must not index or summarize the absent result. The
service observer delivers its terminal record only after that event and final
record lookup.

Durable finalization success is latched before observer cleanup. The pump closes
the observer exactly once on every exit path; a later `close()` exception marks
pump health degraded but cannot rewrite an already-committed terminal row or
change the delivered terminal audit axis.
Before cleanup it closes the queue-admission gate, completes discarded waiters,
and drains every queued command. Observer cleanup may still be visibly pending,
but a broken prefix cannot leave large envelope payloads retained by a terminal
hub.

The production composition derives that cutoff as six seconds from the history
writer's five-second retry bound. History retries for strictly less than the
generic serialized-writer bound: it is an independently degradable axis, so
exhausting it leaves the committed prefix incomplete and reports an honest
`audit=DEGRADED`; every audit and shutdown bound scales from it. Service
shutdown allows twelve seconds: the cutoff plus a complete pump-owned writer
retry and one second of margin. Tests pin the strict inequalities so changing
any constituent bound cannot silently make ordinary late finalization outlive
shutdown, and pin the shutdown ceiling so it cannot grow back into a visible
hang.

The audit *offer* bound is separate and does not scale with finalization.
Finalization must outlast a writer retry so a late but legitimate commit is not
falsely degraded; offer exists only so a wedged audit writer degrades quickly
rather than stalling the emitting workflow thread while its bounded queue is
full. Sharing one knob made raising the former silently multiply the latter, so
the two are now independent constructor arguments with their own regression.

The implemented observer seam is structural and core-typed, so `db` need not
import dispatcher: `on_event(Envelope)`, idempotent `flush()`,
`finalize(OperationResult)`, and `close()`. The composition root supplies an
observer factory. The pump invokes
these methods on a bounded daemon worker, catches observer exceptions, and
stops producer backpressure after the injected timeout by setting
`audit=DEGRADED`. Failure while the composition root constructs or opens the
observer is isolated the same way: admission continues with a degraded-audit
sentinel, so history availability cannot decide whether domain work runs.
If the audit thread never receives an identity, its observer is closed once and
the original start failure escapes; a secondary close failure is retired and
cannot replace it. If the thread did start before `start()` raised, that thread
keeps the observer and performs the normal exactly-once close. Internal empty/
full queue control signals remain ordinary local control flow rather than
general exception-graph owners.
Pump shutdown spends one monotonic deadline across both enqueueing its stop
command and joining the worker; queue delay cannot silently grant a second full
join allowance.

## Session Store

`SessionStore` accepts exact `StoredSessionRecord` values: a separate frozen,
slotted core metadata/result contract with neither a payload field nor a
live-record backreference. Its exact shape lives in `core/session.py`.
Dispatcher explicitly projects that value before admission's `put()` and every
later `put()`, including pause snapshots and the terminal record before audit
finalization supplies its result. This does not weaken `SessionRecord`:
nonterminal live records still require opaque bytes, and terminal live records
require null. The projection retains the full `OperationResult` by identity,
including independent filesystem/recording/audit/cancellation axes, item and
phase detail, errors, recording issues, omission counts, and review-limit
witnesses; it does not substitute a terminal summary. `result=None` remains
valid during state-before-result settlement.

The protocol's `load_all()` returns stored metadata, not live records.
Implementations must reject live records, lookalikes, and subclasses with extra
state; `InMemorySessionStore.put()` enforces the exact concrete type before
changing its table. The active M0/M1 store is process-local and exposes its
accepted metadata through diagnostic `snapshot()`, while `load_all()` returns
`()`. Dispatcher `get()`/`list()`, queued work, resume, and paused cancellation
use the authoritative live table, never a stored row. A later failed write can
therefore leave stale metadata but cannot select an old continuation. An
admission write that accepts and then raises is still unadmitted: rollback/drop
are attempted, and failed cleanup retains ownership for retry without
publication or scheduling.

Terminal live records and stored metadata remain until an exact dispatcher
`close(session_id)` succeeds; successful shutdown alone does not drop the store
rows. The web adapter may invoke close after terminal presentation while
retaining its process-live task, or as part of task close; dispatcher knows
neither case. History remains the durable trail. M1 has no durable session rows
to migrate, and reopening still loses process-live sessions and requires fresh
work. A custom/legacy backend with old payload-bearing rows must separately
verify their retirement or migration before claiming that its existing contents
meet the new contract. Projecting new writes cannot retroactively scrub such
rows or make a failed `drop()` an erasure guarantee.

M2 restart recovery is not enabled by swapping in a SQLite metadata store.
It requires a separately designed protected continuation/recovery-store
contract, explicit recovery and retention rules, unique durable queue ownership,
and fresh workflow authority/custody reconciliation before pending re-admission
or `RUNNING`→`INTERRUPTED` recovery. The current execution-v7 continuation and
its transient attestations are not a durable recovery format. Exact active
continuation and event/database versions remain owned by
[M1_BRIDGE.md](M1_BRIDGE.md); none changes for this metadata boundary.

### Stored-record retention classification

Under [DEFENSE.md](DEFENSE.md) §7, the changed representation is classified as
follows, separately from transport-memory measurement authority:

- `session_id`, `kind`, `state`, `supports_pause`, `admission_order`,
  `created_at`, `started_at`, and `ended_at` are metadata references/values with
  the live record's lifecycle nullability. `InMemorySessionStore._records` maps
  each session id to its latest accepted stored wrapper; replacement retires
  that mapping's previous value, and successful close drops it. No new
  retained-session-count or byte ceiling is claimed.
- `resources` shares the live record's immutable sorted resource tuple.
  `result` is null or shares the existing full result graph by identity, without
  a second detail graph. Its result contract is unchanged.
- Continuation bytes and a live-record backreference are structurally absent.
  The separate `Dispatcher._records` map remains the live continuation owner;
  its representation has not changed.

The stored wrappers and store table are outside the frozen SH-G-8 transport roots
(replay, subscribers, and adapter queues); their validators, corpus, and byte
ceiling are unchanged. Field-shape and fault tests establish the store handoff
contract, not a total-memory reduction or a new measured acceptance ceiling.
The shared full result remains a subject-scaled terminal artifact, separately
observed through live dispatcher result roots. The terminal-artifact and whole-
runtime gates (BR-G-45 and SH-G-15) remain open; this change claims neither bound.
Contained store-write and custody-release failures retain only separate sticky
Boolean failure markers. The dispatcher does not retain the exception, its
arguments, attributes, cause, context, or traceback: any of those can keep an
earlier live record or full workflow graph reachable after session close.
Failed-admission cleanup follows the same rule with one sticky Boolean marker;
each successful cleanup step clears its rollback, stream, or hub reference
immediately even when a different step still needs retry. The single retained
owner therefore contains only unfinished cleanup capabilities, its generated
session id, one store-pending bit, and the failure marker. While cleanup runs,
one exact thread attempt is also retained through actual thread exit; a dead
attempt is reaped before admission capacity is released or shutdown completes.
These markers do not change filesystem outcomes, store fallback, release
order, or the existing shutdown result. A failed audit-observer factory also
retains no initiating exception: its sentinel raises only a fresh fixed error,
keeping the existing failed-prefix audit behavior without retaining factory
frames.
Caller-owned exceptions and audit observers
may still reference earlier records; this boundary does not promise
whole-process or secure-memory erasure. BR-G-45 remains open.

Dispatcher construction occurs before any desktop task exists. An
unsuccessful scheduler-thread construction and an independently injected second
fault inside the otherwise contained fixed-result settlement escape to their
caller or thread hook; they are not retained task artifacts and this boundary
does not convert them into synthetic lifecycle truth.

Queued execution carries the exact core `Commitment` defined by
[M1_BRIDGE.md](M1_BRIDGE.md). Workflow admission validates it and freshly
preflights; dispatcher neither reconstructs nor reinterprets the commitment.
Replanning after wakeup produces a material-difference review; it is not a
silent replacement.
Contending committed sets start in commit order on every declared resource,
even when the earlier set is also waiting on another resource; disjoint-volume
sets may start as soon as their volumes are free. A queued session discarded before running
must deliver its generic discarded/unrun terminal detail to the admission-time
history observer before its live record is dropped; dispatcher never imports or
calls history directly.

The terminal is `CANCELED` with `Disposition.UNRUN`; ordinary cancellation after
work is `CANCELED+RAN`, and preflight refusal is `REFUSED+UNRUN`. A compound
workflow may preserve filesystem `COMPLETED|FAILED` with `canceled=true`;
`result_terminal_state()` is the only lifecycle projection and still settles
the record as `CANCELED`. Dispatcher forwards these core values without
learning domain meaning or inferring from an empty operation list.

## Teardown

Stop admission, request drain/cancel under policy, continue event delivery,
flush session store/required observers, wait without blocking the presentation
thread's terminal dispatch, and verify all locks released. A deadline produces
an explicit incomplete-shutdown result; it never kills unrelated user Office or
application processes. Terminal state alone is insufficient for a complete
shutdown: every generation must also retire and both lease/reservation maps must
be empty. A canceled noncooperative acquisition remains named in `unfinished`
until its owning worker acknowledges control and retires.

## Expectations

- Core owns states, events, context, store protocol, and generic records.
- Composition root provides registry, lock provider, clock, store, and event
  capacity policy.
- Workflows declare resources and deserialize their own opaque request.
- Interfaces only call this public contract and subscribe. Their task registry
  may serialize sessions and retain presentation artifacts, but it does not
  manage a second domain session lifecycle.
- History attaches as the admission-time audit observer; its failure is loud but
  never rewrites filesystem or ledger truth.

## Implemented M0 Layout

- `core/session.py`: lifecycle table, checkpoint signals, generic result,
  session record/store protocol, and sole terminal-producing runner.
- `core/events.py`: versioned M0 bodies/envelopes and explicit schema rejection.
- `dispatcher/contracts.py`: opaque registration, audit, control, and shutdown
  contracts.
- `dispatcher/store.py`: honest process-local store.
- `dispatcher/custody.py`: sorted Windows named-mutex custody and portable test
  fallback.
- `dispatcher/event_bus.py`: per-session sequencing, replay, progress
  coalescing, subscriber ejection, and audit finalization.
- `dispatcher/dispatcher.py`: FIFO admission, control, runner integration,
  record retention, explicit close, and teardown.

## PoC Hardening

Generic custody replaces GUI-wide “another task” state as the source of truth.
Typed terminal/refusal prevents zero-op guard refusal from rendering success.
Event throttling prevents per-MiB UI floods. One session runner prevents stale
worker releases, close-before-thread-finished races, shutdown deadlock, and
duplicate terminal paths from being reinvented by each interface.
