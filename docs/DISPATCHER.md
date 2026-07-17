# Dispatcher Module

Status: draft contract. Priority: M0 in-memory session store plus real safe
custody; M2 durable queue/reconciliation. DR-02, DR-03, DR-09, DR-13, and DR-17
must be resolved at their indicated gates.

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
```

An injected registry maps opaque kind to a generic callable/capability adapter;
dispatcher does not introspect domain request fields. Admission receives a
generic required-resource declaration and opaque serialized workflow payload.

## State And Runner Ownership

Dispatcher enforces core's one legal transition table. The generic session
runner owns start/end timestamps, exception containment, resource release, and
preferably exactly-one terminal emission per DR-03. Modules return typed opaque
results and emit nonterminal events through `RunContext`.

Pause behavior must follow DR-02: drain to a safe boundary, retain an opaque
continuation, exit/release custody, and resume through fresh workflow preflight.
It must not leave a blocked stack holding hidden handles while reporting
`PAUSED`. Cancel requests are cooperative but terminal cleanup/release is
unconditional.

## Admission And Volume Scheduling

Required local physical-volume ids are sorted deterministically before locks to
prevent deadlock. Sessions with disjoint required volumes may run concurrently;
contenders queue. Planning sessions may release locks when complete; execution
reacquires and revalidates volumes.

Per DR-13, cross-process physical-volume exclusion is required before any M0
mutation. This is distinct from M2 durable queue ownership. Unsupported or
ambiguous volumes are refused, not scheduled optimistically. Network-share
coordination remains unavailable and mutating sessions on such roots are refused
unless a separate safe guard exists.

Custody has one owner: dispatcher/session runner. Executor never releases locks.
Every terminal, pause-drain, admission failure, workflow exception, observer
failure, and orderly teardown path releases exactly the acquired set.

## Events And Subscription

Dispatcher assigns envelope timestamp/schema/sequence and fans out events.
Progress is lossy/coalescible; reliable state/item/terminal delivery follows the
finalized DR-09 capacity policy. Subscribers attach independently so a slow UI
cannot block history or producer. Late subscribers receive current state plus a
bounded tail/detectable gap—not a false promise of full replay.

History attaches at admission before workflow events. Subscriber exceptions are
isolated and surfaced; they do not crash the producer or silently remove a
required audit subscriber.

## Session Store

`SessionStore` persists/retains generic `SessionRecord` with opaque workflow
blob. Dispatcher may serialize the blob but never deserialize domain content;
the registry/workflow adapter does that after selection.

M0 `InMemorySessionStore` provides process-local task state and no restart
reconciliation. M2 `SqliteSessionStore` adds reload, durable pending queue,
single queue-owner lock, and `RUNNING`→`INTERRUPTED` reconciliation when owner
process/custody is dead. DR-17 must define terminal retention and `drop()` before
durable UI tasks depend on it.

Queued execution still requires a reviewed/authorized immutable plan and fresh
preflight. Replanning after wakeup produces a material-difference review; it is
not a silent replacement.

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
- History attaches as an observer and follows DR-16 failure semantics.

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
  state corruption.
- Disjoint-volume sessions overlap; shared-volume sessions serialize in
  deterministic lock order; cross-process M0 mutation contention is actually
  refused/queued according to DR-13.
- Fault injection at admission, lock acquisition, workflow start, every event,
  pause, cancel, terminal, store write, subscriber failure, and teardown releases
  exactly acquired resources and emits one terminal under DR-03.
- Paused session holds no volume lock/open workflow stack and resume starts with
  fresh preflight under DR-02.
- Progress flood remains bounded/coalesced; reliable-event stress follows DR-09
  with no silent loss or producer deadlock.
- Late subscription returns current state/tail and exposes sequence gaps.
- Opaque blobs round-trip through store without dispatcher deserialization.
- M0 process restart loses in-memory sessions honestly and requires rescan;
  M2 simulated kill marks only orphan running records interrupted and safely
  re-admits pending work.
- Queue owner is unique across processes; volume locks remain independent.
- Orderly teardown completes without UI-thread deadlock and reports any session
  that could not drain within policy.
- Terminal retention/drop behavior satisfies finalized DR-17 and never erases
  required audit history.

