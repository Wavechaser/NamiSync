# Dispatcher Module

Status: M0 implemented and acceptance-tested. M1 Stage 4 adds a generic
registration-owned canceled-settlement seam for already-started opaque work;
the dispatcher remains domain-blind. M2 durable queue ownership, SQLite session
persistence, and startup reconciliation remain deferred.

## Purpose

Dispatcher admits, schedules, controls, and observes generic sessions. It knows
session ids, states, required resources, opaque workflow kind/request/result
payloads, and event delivery classes. It does not know what sync, verify,
baseline, import, or ingest means and never imports modules, database, or
workflows.

## Public Contract

```python
submit(kind, request) -> SessionId
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
record, blocks new subscriptions, and waits for audit/subscriber cleanup before
dropping the session-store row or any in-memory ownership. If cleanup exceeds
the injected audit timeout it raises `TimeoutError` and retains the record, hub,
controls, and publication lock for a safe retry. `shutdown()` stops admission,
attempts cancellation first for every session whose publication and hub gates
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

## Admission And Volume Scheduling

Required local physical-volume ids are sorted deterministically before locks to
prevent deadlock. Sessions with disjoint required volumes may run concurrently;
contenders queue. Planning sessions may release locks when complete; execution
reacquires and revalidates volumes.

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

A per-session publication gate spans each persisted lifecycle transition and
its matching reliable `StateChanged`. Later transitions cannot publish first or
make the hub's current-state replay regress, while unrelated sessions remain
independent. Dispatcher also serializes hub subscription registration with
terminal `close()` and shutdown cleanup: if subscribe wins, cleanup shuts that
stream; once cleanup claims the session, subscribe returns `SessionNotFound`.
A closed session cannot retain a newly orphaned stream.

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
Pump shutdown spends one monotonic deadline across both enqueueing its stop
command and joining the worker; queue delay cannot silently grant a second full
join allowance.

## Session Store

`SessionStore` persists/retains generic `SessionRecord` with opaque workflow
blob. Dispatcher may serialize the blob but never deserialize domain content;
the registry/workflow adapter does that after selection.

M0 `InMemorySessionStore` provides process-local task state and no restart
reconciliation. It retains current-process records for `get()`/`list()` while
deliberately returning `()` from `load_all()`, so it cannot accidentally claim
restart durability. M2 `SqliteSessionStore` adds reload, durable pending queue,
single queue-owner lock, and `RUNNING`→`INTERRUPTED` reconciliation when owner
process/custody is dead. Terminal records stay in the live session table until
the task is explicitly closed, then `drop()` removes them; history remains the
durable trail.

Queued execution accepts only a `Commitment` matching plan fingerprint and
selection digest, and always freshly preflights. Replanning after wakeup
produces a material-difference review; it is not a silent replacement.
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
application processes.

## Expectations

- Core owns states, events, context, store protocol, and generic records.
- Composition root provides registry, lock provider, clock, store, and event
  capacity policy.
- Workflows declare resources and deserialize their own opaque request.
- Interfaces only call this public contract and subscribe; they do not manage a
  second session lifecycle.
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

## Acceptance Criteria

- Import-linter and symbol scan prove dispatcher imports core only and contains
  no domain activity names/methods.
- Exhaustive transition/control tests reject illegal pause/resume/cancel without
  state corruption; pause capability tests accept execution/verify/baseline and
  refuse scan/plan/import by generic registration metadata.
- Disjoint-volume sessions overlap; shared-volume sessions serialize in
  deterministic commit/lock order; cross-process M0 mutation contention is
  actually refused/queued by the OS-level lock.
- Fault injection at admission, lock acquisition, workflow start, every event,
  pause, cancel, terminal, store write, subscriber failure, and teardown releases
  exactly acquired resources and emits one terminal from the core runner.
- Cancellation during PAUSING snapshot drain, PAUSED, and resume→PENDING invokes
  an opted-in settlement callback at most once; malformed settlement fails
  loudly, repeated cancel is rejected, and same-resource followers prove
  custody release.
- Paused session holds no volume lock/open workflow stack and resume starts with
  fresh preflight at the back of the volume queue; successful pause settlement
  and live `PAUSED` publication follow the durable audit-flush attempt.
- Progress flood remains bounded/coalesced; history delivery backpressures only
  at a safe boundary until timeout, then degrades `audit`; an overrun
  non-history reliable subscriber gets `Gap` and ejection rather than silent
  loss.
- Audit windows flush on the original age deadline even under continuous
  events; clean stop flushes once, flush failure retains only the committed
  prefix, and observer cleanup runs exactly once without rewriting successful
  finalization.
- Late subscription returns current state/tail and exposes sequence gaps.
- Opaque blobs round-trip through store without dispatcher deserialization.
- M0 process restart loses in-memory sessions honestly and requires rescan.
- **M2 gate:** simulated kill marks only orphan running records interrupted and
  safely re-admits pending work; the queue owner is unique across processes and
  remains independent from volume locks.
- Orderly teardown completes without UI-thread deadlock and reports any session
  that could not drain within policy.
- Terminal records survive until explicit close; a timed-out audit cleanup
  retains hub/store ownership for retry. Queued discard is observed as
  `CANCELED+UNRUN` before `drop()` and never requires a dispatcher-to-history
  import or string parsing.

Current verification covers the non-M2 criteria with named regression/fault tests:
focused core/dispatcher tests exercise the transition/control matrices,
concurrency, pause/resume/cancel, pre-pause outcome retention, opacity, bounded
events/audit, store/lock/adapter/observer faults, teardown deadlines, and a real
subprocess holder-kill mutex recovery. The full shared suite and import-linter
remain the release gate because registry adapters and core event types are
cross-module contracts.
