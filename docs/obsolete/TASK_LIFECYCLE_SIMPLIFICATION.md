# Task Lifecycle Machinery Simplification

**Standing (2026-09-03): archived completed delivery record.** This document
records the closed denominator, stop rules, guard evidence, and implementation
history for the task-lifecycle simplification. It is not active authority for
new work.

This repository document is the sole maintained plan for the task. The older
`.codex` plan is a historical snapshot and is neither updated nor used as a
second completion authority.

This is subtractive work. A regression is an observable change at a real
boundary; a red test may not be one, and a green suite does not prove its
absence. Completion requires both boundary invariance and positive proof at
each new authority. It fails if cleanup, receipt, association, or observation
machinery is merely renamed or moved.

## 1. Fixed ownership and lifecycle

| Concern | Authoritative owner | Explicit exclusion |
| --- | --- | --- |
| Session admission, custody, lifecycle, concurrency | Dispatcher | Task/drain presentation state |
| Domain effect, domain-effect receipt, session association, compensation | Service/application lifecycle | Transport delivery and response replay |
| Stream, callback, thread, subscription lifetime | Service observer | CLI/web lifecycle |
| Queueing, drain, connection, response delivery/replay | CLI/web adapters | Session custody or effect cleanup |

One application settlement transition requests teardown. The observer alone
releases its stream/callback/thread; the dispatcher alone closes custody.
Application state retains exact association, terminal-reconciliation truth,
the monotone settlement target, and a coarse whole-operation in-flight fact,
never physical-step progress, an `EventStream`, sink, observer thread, or
observer rollback callback.

Normal release is:

`adapter delivery fact -> application settlement -> observer release confirmed -> dispatcher close -> detail retirement -> optional plan/task retirement`

A logical settlement retries its fixed cleanup sequence as one whole
operation. Cleanup calls may repeat; a completed observable effect may not.
The application retains no per-step acknowledgement or resumption cursor.
Each physical owner instead exposes an exact-subject, monotone operation whose
postcondition can be ensured again without recreating retired state. One
whole-operation application claim excludes a concurrent peer for the same
association while disjoint associations remain independent.

### LC-1b cleanup replay and supported fault model

The supported recovery unit is the same-process command operation, not an
individual cleanup call. A cleanup owner may raise before changing its state,
after moving closer to its postcondition, or after reaching the postcondition
but before the caller observes success. An interrupt may likewise occur
between an owner return and application finalization. In each case the next
same-command or authorized close retry starts the fixed cleanup sequence from
its beginning. Process termination may lose the process-local task and receipt
state under the existing residual; LC-1b adds no restart journal or
cross-process recovery guarantee.

That interruption rule applies only to the fixed cleanup owners enumerated
below. LC-1b does not add recovery across the inherited call-frame gap between
`Dispatcher.submit()` returning and application start publication beginning;
closing that gap would require a separate Dispatcher/application admission
reconciliation contract and is not claimed by this reduction.

Every replayed cleanup operation must satisfy all of these rules:

- it names the exact association, detail owner, or plan token established by
  admission, never a newly looked-up successor;
- absence is the required postcondition and cannot recreate state;
- one successful state transition may have multiple call attempts, but it may
  produce no extra event, persisted mutation, filesystem effect, terminal, or
  unprompted transport delivery. Each repeated bridge command still receives
  exactly its specified identical replay response;
- failure leaves either the original state or a state closer to absence, and a
  retry remains valid from either state; and
- application locks are not held across observer, dispatcher, or runtime
  calls.

The finite cleanup ownership rules are:

| Operation | Replay rule |
| --- | --- |
| Observer release | Repeated exact-session release ensures that the observer lookup, stream, callback, and thread are absent. A live join timeout remains retryable; already absent is success. |
| Dispatcher close | `Dispatcher.close` remains globally strict. Only an application settlement that already holds the exact sealed association may interpret `SessionNotFound` as custody already absent. Dispatcher-owned close retry remains inside Dispatcher. |
| Runtime detail retirement | Repeated exact `(kind, request_id)` retirement is an owner-locked `pop(key, None)` and therefore ensures absence. |
| Plan retirement | Exact `PlanToken` retirement remains mutually exclusive with plan mutation. Runtime plan state, service selection state, mutation receipts, and application plan state may each be ensured absent again, but no retry may retire a successor plan identity. |
| Application finalization | Repeated finalization against the exact association token converges on the same session-released or task-retired logical state and emits no external effect. |

Admission rollback uses the same algebra: one whole-operation rollback claim
replays observer release, exact detail retirement, and exact unpublished
association retirement from the beginning. It retains the attachment identity
and actual cleanup liabilities, not a rollback-step cursor. Dispatcher
`_AdmissionCleanup` predates LC-1a, stays wholly Dispatcher-owned, and is not
changed in LC-1b; it is only a later simplification candidate.

### Retention and adapter response replay

- Preserve 48 active desktop task effects.
- Preserve 48 close-response tombstones and their LRU behavior.
- Preserve at most 48 adapter `start_plan` response-replay entries. They
  retire on task close, failed provisional discard, or adapter/service
  shutdown. Failed or refused starts are not retained for later replay.
- Add no receipt-capacity error and do not revive the retired 4,096-receipt
  design.
- Task-bound start receipts retire on task close, not terminal-session release.
- Direct start receipts retire on successful direct `close_session`.
- Selection-mutation receipts survive artifact replacement and retire on plan
  drop or service shutdown.
- Other application receipts retire with their owning session, plan, task, or
  service shutdown. No aggregate-byte guarantee is introduced.
- The application is the sole **domain-effect receipt** owner. The adapter may
  retain a bounded `start_plan` response-replay cache containing only command
  id, wire intent, in-flight/result delivery state, and `TaskStartView`. It
  contains no resolved roots, association, compensation, observer resource, or
  cleanup authority.

A delivery factory may create provisional adapter queue state before
admission. Its exact adapter-local state machine is
`absent -> provisional-unpublished -> active`. Provisional state is unreachable
from drain and replay. The adapter call frame discards it locally on failure;
the service/application never retains or invokes an adapter rollback.
Concurrent adapter close marks provisional delivery closed and keeps it only
until the admitted call returns. Every admitted session, including each of the
six direct CLI start forms with no desktop task, receives one application-level
association with `task_id=None`. A direct start with no command id creates no
receipt; a non-null command id also creates its direct receipt. Direct sessions
consume no desktop-task slot and call no delivery factory.

### Accepted internal modules

- `namisync/interfaces/task_port.py`: adapter-facing task views and narrow
  `TaskLifecyclePort`.
- `namisync/interfaces/task_lifecycle.py`: private application aggregate,
  domain-effect receipts, association, compensation, and settlement.
- `namisync/interfaces/session_observer.py`: `SessionObserver` and private
  `SessionSubscription`.

The task port exposes only task-bound plan start with a delivery factory, exact
task/session reobservation, terminal-session release, and task close. It
exposes no raw unsubscribe/session close/plan drop, dispatcher, compensation,
stream, or rollback primitive.

External commands remain exactly `start_plan`, `next_events`,
`release_terminal_session`, and `close_task`. CLI `receive(update)` remains a
push callback.

### Non-goals

- No bridge command, payload, error, response, retry, or revision change.
- No CLI stdout/stderr/exit, callback-shape, or push-timing change.
- No event schema/order/sequence/`Gap`/terminal/cardinality change.
- No persisted byte, schema, data epoch, or filesystem-effect change.
- No change to replay 128, subscriber 64, or adapter 64 capacity; no
  backpressure, batching, progress replacement, or drain timing change.
- No scheduler, reservation, lease, worker-generation, fairness, or
  multi-session concurrency change.
- No mutable `_SessionSlot`; no service-owned queue, drain claim, delivery
  generation, or connection state.
- No opportunistic test compression, unrelated cleanup, or extension of the
  closed `../SIMPLIFICATION.md` register.

An event-shape or volume change invalidates the 128/64/64 evidence and stops
this register for separately measured work.

## 2. Boundary, defect, and stop policy

Real boundaries are bridge responses; CLI stdout/stderr/exit; delivered event
streams; persisted bytes; and filesystem effects.

1. **T1:** temporary boundary-invariance corpus, frozen before production edit.
2. **T2:** baseline-invariant detectors that pass untouched production plus
   introduced-guarantee detectors installed only with their new owner.
3. **T3:** ordinary suite, necessary but insufficient.

`DISC-B1` and `DISC-B2` are observation-only discovery over named baseline
transitions. They close when the transitions are observed and recorded; they
do not assert target architecture against the untouched tree.

- A checkpoint-caused defect is fixed before its mergeable commit.
- A preexisting substantive defect stops migration, is recorded in `BUGS.md`,
  and requires adjudication before a separate fix or explicit acceptance.
- Do not repair a preexisting defect merely to restore green.
- Findings never add register rows. Repository mechanism/defect thresholds
  remain active.

| Stop class | Tier and detector |
| --- | --- |
| `LS-1` silent loss/duplicate | **Baseline, corrected in LC-0b.** `test_ls_1_delivery_has_no_silent_loss_or_duplicate` barrier-forces ejection and recovery, maps every delivered reliable producer event exactly and at most once, requires every missing reliable producer sequence to fall within a finite interval announced by a delivered `Gap`, and checks terminal uniqueness/last separately. |
| `LS-2` wrong/unreachable session control | **Baseline, LC-0.** `test_ls_2_session_control_reaches_only_corresponding_dispatcher_record` proves service `pause`/`resume`/`cancel` mutate only the exact dispatcher record; unknown or retired sessions mutate none. |
| `LS-3` false terminal reconciliation | **Introduced, LC-1a.** `test_ls_3_terminal_reconciliation_matches_dispatcher_truth` compares delivered Terminal/record with dispatcher truth before settlement; injected disagreement prevents close and success replay. An injected internal disagreement alone is not a baseline defect; an actual supported baseline disagreement is. |
| `LS-4a` missing/duplicate admission rollback | **Baseline in LC-0; reanchored in LC-1b.** `test_ls_4a_admission_rollback_owner_fault_retries_from_observer` faults observer release and detail retirement before and after their transitions; adoption rejection and failed publication have focused composition witnesses. Calls may repeat while each exact transition occurs once and unrelated subjects remain untouched. The unchanged `test_ls_4_dispatcher_admission_cleanup_converges` retains D1-D4 at the Dispatcher owner. |
| `LS-4b` missing/duplicate application settlement effect | **Introduced in LC-1a; redefined and reanchored in LC-1b.** `test_ls_4b_whole_operation_cleanup_replay_converges` faults each finite owner before its transition. Post-effect observer, Dispatcher, detail, and plan failures are proved respectively by `test_cleanup_post_effect_interrupt_replays_calls_not_effects`, `test_cleanup_retry_uses_current_owner_truth_not_application_progress`, `test_lifecycle_cleanup_sequences_are_fixed_and_owner_idempotent`, and `test_s6_cleanup_replay_repeats_owner_calls_not_effects`. The S6 witness explicitly repeats observer, Dispatcher, detail, and plan calls while each physical transition remains unique. Exact final absence has no missing, repeated, or wrong-subject observable effect. `test_ls_4b_whole_operation_cleanup_singleflights_concurrent_callers` proves one active whole-operation claim. Repeated invocation of an idempotent cleanup method is not itself an LS-4b consequence. |
| `LS-5` retained stream/callback | **Baseline, LC-0.** `test_ls_5_release_retires_stream_and_callback` proves observer lookup and subscriber custody disappear, callback count cannot advance, and a weak sink owner is collectible. |

LS-4a's F1-F5/R1-R4 table is the pre-migration characterization of machinery
LC-1a removes. LC-1b deletes that step-specific harness only after reanchoring
its surviving consequence at the exact application owners above; Dispatcher
D1-D4 remains unchanged. The enduring stop-detector set after LC-1b is LS-1,
LS-2, LS-3, the reanchored LS-4a and LS-4b, and LS-5.

Synthetic `Gap` envelopes are recovery-control values, not producer-event
identities for cross-subscription uniqueness or ordering. Their envelope
sequence may repeat or move backward when recovery restarts at
`first_missed_seq`; consumers retain the last accepted non-`Gap` producer
cursor. Within-response validation and producer-event sequence guarantees are
unchanged. No active normative contract promises globally monotonic raw
envelope arrival across `Gap` recovery.

### LS-4a finite baseline fault domain

| Row | Injected fault | Required baseline observation |
| --- | --- | --- |
| F1 | Pre-effect session-attachment refusal | Only the application attachment attempt fails; there is no attachment state to roll back. Any dispatcher-local failed-admission cleanup remains governed by D1-D4 rather than being declared a no-op. |
| F2 | Detail-owner installation | Completed attachment rolls back once; stream retires; no observation or publication remains. |
| F3 | Sinkless stream retirement | Attachment/detail rollback completes; baseline stream close records three calls: one failure, one physical transition, and one idempotent follow-up. |
| F4 | Observer adoption | Rejected stream retires; detail and attachment roll back; nothing publishes. |
| F5 | Dispatcher publication after attachment | Observation, detail, and attachment roll back in the existing order; no session remains published. |
| R1 | Observer release fails while retaining the sink | Two public retry callers share one dispatcher cleanup attempt; only observer release retries, then gated owner rollback proceeds. |
| R2 | Observer release raises after retiring the sink | Retry recognizes physical retirement and does not repeat observer release. |
| R3 | Detail rollback fails | Observer remains completed; only exact detail retirement and then gated owner rollback retry. |
| R4 | Attachment-owner rollback fails | Observer and detail remain completed; only owner rollback retries. |
| D1 | Dispatcher admission rollback callback fails once | Callback may have two attempts and one success; already completed cleanup siblings remain at one. |
| D2 | Dispatcher subscribed stream close fails once | Stream close may have two attempts and one success; already completed siblings remain at one. |
| D3 | Dispatcher hub close fails once | Hub close may have two attempts and one success; already completed siblings remain at one. |
| D4 | Dispatcher store drop fails once | Store drop may have two attempts and one success; already completed siblings remain at one. |

Before freezing T1, audit every LC-0 guard with: **Can this pass on the
untouched baseline without production changes?** If not, move it to the
checkpoint introducing the guarantee. T1 freezes only observable real-boundary
behavior.

## 3. Complete service-entry and retirement census

| Entry | Authority/effect | Retirement |
| --- | --- | --- |
| `start_plan` | Plan request, receipt, association, optional task | Direct receipt at direct close; task receipt/plan survive terminal release and retire at task close; plan also on drop/service close. |
| `start_execution` | Plan/selection read, commitment, receipt, session/detail association | Receipt/detail on session close; plan/selection on drop/service close. |
| `start_inventory` | Receipt, session, inventory detail | Session/service close. |
| `start_baseline` | Receipt, session, inventory detail | Session/service close. |
| `start_verify` | Receipt, session, inventory detail | Session/service close. |
| `start_rebaseline` | Receipt, session, inventory detail | Session/service close. |
| `mutate_selection` | Plan authority and per-request receipt | Survives artifact replacement; plan drop/service close. |
| `pause` | Exact live session control | No receipt; ends when released or dispatcher rejects. |
| `resume` | Exact live session control | Same as pause. |
| `cancel` | Exact live session control | Same as pause. |
| `reobserve` | Exact association and subscription replacement | Old subscription releases before new adoption; association remains. |
| `unsubscribe` | Observation release only | Idempotent; association/custody remain. |
| `close_session` | Observer, dispatcher, receipt, and detail settlement | Direct close retires session state, not plan; task release retains task/plan receipt. |
| `drop_plan` | Plan, selection, mutation receipts | Never substitutes for observer release or dispatcher close. |

Location resolution is an additional census row, not a fifteenth method. A
fresh refusal with no retained response creates no application receipt,
association, observer, or dispatcher session. A retained successful response
may replay before resolution after its original slots expire or are evicted.
This is not cached refusal replay.

## 4. LC-0 guard contract

### T1 temporary corpus (retired at LC-6)

`tools/task_lifecycle_audit.py`, `tools/task_lifecycle_baseline.json`, and
`tests/test_task_lifecycle_audit.py` used production bridge dispatch, real
service/dispatcher/observer/task-drain composition, and a real plan-only
filesystem fixture. They captured:

- canonical envelopes for all four commands and identical replay of start,
  terminal release, and task close;
- every delivered update/terminal record for one complete plan session,
  including exact order/body/`Gap`/terminal-last;
- a fixed declined-plan CLI stdout, exact stderr, and exit;
- before/after source/target manifests with file size, SHA-256, and mtime;
- existence and SHA-256 for ledger/history main files and sidecars.

The committed corpus used one fixed canonical fixture root and injected a fixed
1 TiB free-space result into the declined-plan CLI fixture. Those are declared
fixture inputs, not normalization. Normalize only temporary roots, the three
explicit IDs returned by the production start as generated opaque identities,
and timestamps by stable occurrence identity. Fixture-owned request/drain IDs
and unrelated 32-hex text stay exact. Never normalize event bodies/order,
errors, dispositions, CLI
prose/exits, contents, persisted hashes, or repeated-id relationships.
Self-tests corrupted each boundary family. Three fresh-process captures
normalized identically. The corpus was frozen once and deleted only after its
final LC-6 match.

### Corpus format and re-freeze authority

`format_version` identifies only the corpus JSON schema. `FORMAT_VERSION`
remains exactly 1 and the frozen baseline, normalization, fixture inputs,
captured boundary domain, fixed fixture root, and fixed free-space input remain
byte-exact through the final pre-LC-6 verification. LC-1a through LC-5 may not
change them. A corpus-schema deficiency is not permission to update the oracle
from an implementation tree; changing the number alone authorizes no other
change.

Any legitimate schema change stops the active checkpoint and requires explicit
user/register adjudication plus a new guard-only row. In an isolated checkout
of the LC-0a closing commit, whose production tree remains the untouched
`5631066` tree, enumerate the exact schema additions; run the candidate runner
without production changes; prove every overlapping boundary observation is
equal and every added field derives from that untouched baseline; retain all
corruption sensitivity; produce three identical fresh captures; and record the
old/new schemas and hashes. A bump may not accompany production changes. Any
overlap difference, or any re-freeze whose purpose or effect is to make current
implementation output pass, is boundary drift and a checkpoint-owned
regression rather than schema migration.

### Observation-only barriers

- `DISC-B1`: block the CLI callback after a running update, issue cancellation,
  and record whether dispatcher/workflow cancellation advances before callback
  release, callback order, control result, terminal count, and exit.
- `DISC-B2`: block a production bounded-queue offer, begin shutdown, and record
  the untouched transition: delivery closes, its generation invalidates, the
  blocked offer wakes before observation release, current adapter observation
  cleanup then completes, and service close follows. Drain supersession and
  admitted-handler departure remain separately protected adapter-delivery
  behavior; the barrier does not assert their future teardown owner.

### Test disposition

`TASK_LIFECYCLE_TEST_LEDGER.md` is the finite pre-implementation census.
Its AST/name/string procedure closes over exactly seven files and records the
129 baseline behavioral tests, the two authorized selection-race witnesses,
and eight shared helpers. Each changed test is exactly
`mechanism-removed`, `reanchored-owner`, or `boundary-retained`. Reanchor before
deletion; never delete a boundary test, compress unrelated tests, leave
orphaned support, or knowingly uncover supported behavior.

### Pre-change mechanism graph

The baseline graph is intentionally recorded before any production edit:

`bridge command -> TaskRegistry _StartEntry/_TaskReservation -> adapter
session_attachment -> service receipt/detail maps -> dispatcher
AdmissionAttachment/_AdmissionCleanup -> service SessionObserver/_Observation
-> TaskRegistry queue/drain`

Terminal and failure cleanup currently fans back through
`TaskRegistry._Compensation`, `TaskRegistry._TaskCleanup`, and
`TaskRegistry.unsubscribe_all`, which can call service `unsubscribe`,
`close_session`, and `drop_plan`; service then coordinates observer release,
dispatcher close, exact detail retirement, and its receipt tables. The
test-ledger front matter is the exact path-scoped symbol/string search domain
for this graph. The graph is comparison evidence only: LC-1a must delete its
duplicate authorities rather than rename them.

## 5. Closed checkpoint register

| ID | Accepted outcome | Depends on | Verification | Status |
| --- | --- | --- | --- | --- |
| `LC-0` | Ratify this register/census, freeze boundary-only T1, record both observation barriers, and install four baseline T2 detectors. | None | Three identical T1 runs; corruption self-tests; recorded barriers; detector fault self-tests; ordinary/import baseline. | Complete |
| `LC-0a` | Freeze generated-ID equality/distinctness, corpus-version governance, exact LC-6 department retirement, and the retained-guard cost before production work. | `LC-0` | Focused oracle tests; unchanged frozen hash; documentation inspection; no production diff. | Complete |
| `LC-0b` | Settle the LS-1 normative contract, replace its timing-sensitive raw-order assertion with deterministic loss/duplication accounting, and withdraw the unsupported defect classification. | `LC-0a` | Finite normative audit; duplicate/loss self-tests; 30 fresh deterministic runs; T1 and production unchanged; ordinary/import gate. | Complete |
| `LC-1a` | Application becomes sole domain-effect owner; duplicate association/compensation/cleanup authority disappears; bounded adapter response replay and delivery shutdown remain. | `LC-0b` | T1 unchanged; disappearance/test symmetry; structural no-drain-cleanup proof; introduced LS-3 and LS-4b plus enduring T2; affected neighborhood. | Complete |
| `LC-1b` | Replace application cleanup step cursors and marker repair with whole-operation replay over exact, monotone owner operations while retaining LC-1a authority, receipts, association, terminal truth, and plan-retirement exclusion. | `LC-1a` | Finite disappearance list; reanchored LS-4a/LS-4b fault matrices and concurrency detectors; T1/enduring T2; focused, ordinary, and import gates; net-subtractive production diff. | Complete |
| `LC-2` | Observer/`SessionSubscription` solely owns physical observation lifetime without CLI/web timing change. | `LC-1b` | Barrier timing, observer fault matrix, T1/T2, interfaces. | Complete |
| `LC-3` | Compose live/stored session records without lock, concurrency, persistence, or public behavior change. | `LC-0b` only; independent of `LC-2` | Core/dispatcher, exact contained stored identity, T1 persisted bytes. | Complete |
| `LC-4` | Retain parallel maps and close disposable entry feasibility probe with truthful lock-ownership result. | `LC-3` | Scratch entry, finite mutators, AST plus instrumented condition, concurrency, full reversal. | Complete |
| `LC-5` | Run/reverse terminal-field probe inside exact derived twelve-file domain. | `LC-1b`, `LC-2`, `LC-3` | Exact diff, field-flow tests, no residual. | Complete |
| `LC-6` | Integrate/adversarially close and retire only temporary T1. | `LC-1b`, `LC-2`, `LC-3`, `LC-4`, `LC-5` | Final T1 match; enduring tests; ordinary/headed/import/docs/cleanliness. | Complete |

### LC-0a guard-governance amendment

- One normalization test must prove all relationships together with ordered
  `[A, B, A, B]`: repeated declared IDs keep their tokens, distinct declared
  IDs remain distinct in first-seen order, and an undeclared fixed
  opaque-looking value stays exact.
- A literal guard pins `FORMAT_VERSION == 1` in both runner and baseline. The
  re-freeze policy above is the only authorized way to change it.
- LC-6 deletes exactly `tools/task_lifecycle_audit.py`,
  `tools/task_lifecycle_baseline.json`, and
  `tests/test_task_lifecycle_audit.py`, then removes only the latter's `tools`
  department entry. It retains `tests/test_task_lifecycle.py` and its
  `interfaces` department entry, then runs the department-manifest check.
- No production source, frozen baseline, boundary expectation, or test
  disposition changes in LC-0a.

Commit gate: `test(interfaces): harden lifecycle oracle governance`.

### LC-0b LS-1 guard correction

The finite normative audit covered `ARCHITECTURE.md`, `CORE.md`,
`DISPATCHER.md`, `INTERFACES.md`, `HISTORY.md`, `M1_BRIDGE.md`, the core event
contract and validator, `EventHub`/`EventStream`, `SessionObserver`, the browser
drain, and their Gap/recovery witnesses. Producer envelopes have a gap-free
per-session sequence, but no clause extends that promise to synthetic Gap
markers across subscription recovery. The specific rules instead retain the
last accepted non-Gap cursor, recover from exact `first_missed_seq`, and permit
a matching leading recovery Gap. `DISPATCHER.md` names the cost as duplicate
work and a stuttering consumer, not silent loss; the required browser witness
intentionally accepts repeated raw Gap sequence values.

The corrected detector uses explicit barriers: direct session start and
observation precede emission; the first callback blocks; a fixed reliable flood
synchronously ejects the captured 64-slot stream; terminalization remains
blocked until a non-null recovery subscription is installed and its retained
tail is delivered. Synthetic Gap values are excluded from producer-event
uniqueness. A recovery interval ends immediately before the next delivered
producer event, not at the synthetic Gap envelope's sequence. Separate
corruption self-tests prove duplicate reliable delivery and unannounced
reliable loss fail the detector. No production file, T1 artifact, department
entry, capacity, or event mechanism changes in LC-0b; `event_bus.py` remains
untouched.

Commit gate: `test(interfaces): correct lifecycle loss detector`.

### Pre-LC-1a plan-selection retirement fix

A separately adjudicated baseline defect allowed `_selection_state` to install
or refresh state after a successful runtime plan read had lost to completed
`drop_plan`. The supported caller still received the existing `KeyError`;
persisted bytes, filesystem effects, and later readers remained correct. The
only product consequence was shutdown-bounded unreachable selection state and
mutation receipts, although repeated races could accumulate that memory. This
is one defective site beside `save_plan`'s correct retirement-exclusion
pattern, not a repeated mechanism instance.

The baseline repair revalidates plan liveness outside `self._lock` after each
new installation or refresh. A vanished plan removes the entry only when it is
still the exact state installed by that call and re-raises the existing
`KeyError`; an observed replacement preserves revision and receipt lineage,
preserves any concurrently installed successor, and is itself revalidated.
No runtime method runs while `self._lock` is held. This repair introduces no
LC-1a lifecycle machinery and does not restructure selection ownership.

`test_selection_mutation_drop_race_does_not_retain_or_replay` is the sole
regression identity during recovery: it pauses `_selection_state` after its
initial successful plan read, completes `drop_plan`, resumes the mutation,
and proves the existing `KeyError`, zero selection effect, no retained
selection or receipt, and no same-command replay. LC-1a may remove the
temporary `_selection_state` revalidation only after this same regression is
reanchored at the application lifecycle owner and proves retirement exclusion
across the complete mutation receipt/effect operation, or atomic receipt
rejection against a retired plan token. Do not duplicate the regression.
`test_selection_liveness_retry_preserves_concurrent_successor` is a distinct
A→B→C→D identity witness for the cleanup algorithm: neither an observed
replacement nor a later fresh snapshot may overwrite a concurrently installed
successor, even transiently. It receives the same owner-level reanchor
disposition in LC-1a.

Commit gate: `fix(interfaces): close plan selection retirement race`.

### LC-1a recovery protocol and result

Recovery commit `dc94aef` was used only as path-scoped review input through
`git diff 197a2fc dc94aef -- <path>`, never merged or cherry-picked. The fresh
LC-1a branch from corrected baseline commit `c456cf4` has rebuilt and reviewed
the accepted content path by path. Retain the WIP branch until the rebuilt
atomic LC-1a commit passes its remaining ordinary/adversarial closeout gate.
The port and strong indirect import contract remain inside LC-1a. Command
stripes remain only with explicit single-flight and disjoint-command
concurrency proof.

| Path | Recovery status | Required review |
| --- | --- | --- |
| `namisync/interfaces/task_lifecycle.py` | New | High: state model, locking, settlement retry, receipt retirement, retention bounds. |
| `namisync/interfaces/task_port.py` | New | High: exact public surface and absence of raw cleanup capabilities. |
| `namisync/interfaces/service.py` | Existing | High diff against `197a2fc`. |
| `namisync/interfaces/web/drain.py` | Existing | High: retained transport replay versus removed domain authority. |
| `namisync/interfaces/web/host.py` | Existing | High or medium-high: shutdown ordering and DISC-B2 boundary. |
| `namisync/workflows/views.py` | Existing | High despite its size because it participates in LS-3 terminal truth. |
| `pyproject.toml` | Existing | High structural evidence, not routine configuration. |
| `tests/test_service.py` | Existing | High: substantial new-owner acceptance evidence. |
| `tests/test_task_lifecycle.py` | Existing | Discard WIP diff; rebuild from corrected guard version. |
| `tests/test_bridge_service.py` | Existing | Discard WIP diff; rework from the test-disposition ledger. |
| `tests/interfaces/web/test_host.py` | Existing | Medium: shutdown and delivery-withdrawal evidence. |
| `namisync/interfaces/web/bridge.py`, `namisync/interfaces/web/commands.py`, `tests/interfaces/web/_public_view_witnesses.py` | Existing | Low. |
| Register and test ledger | Existing | Rebuild carefully: they carry the completion denominator and evidence. |
| Other explanatory documents | Existing | Recreate only after behavior settles. |

### LC-1a mandatory disappearance and positive proof

| Disappearance | New-owner proof |
| --- | --- |
| `_StartEntry` domain-effect receipt/single-flight authority | Application replays identical resolved intent and rejects conflict; adapter cache retains only the permitted response fields. |
| `_TaskReservation.attached_session_id` authority | Exact lifecycle association for reobserve, terminal release, and task close; correct/wrong/retired identities. |
| Drain `_Compensation` | `test_ls_4a_admission_rollback_owner_fault_retries_from_observer` faults each retained observer/detail rollback owner before and after its transition; the focused attachment/adoption/publication witnesses cover the remaining `_submit_session` seams, and `test_whole_admission_rollback_singleflights_concurrent_callers` proves one exact rollback owner under concurrent retry. Calls may repeat, but each physical transition remains unique. |
| Drain `_TaskCleanup`/progress booleans | LC-1a proved first-unfinished-step retry at the new owner. LC-1b deliberately retires that proof with the progress machinery and replaces it with whole-operation replay/no-duplicate-effect evidence. |
| `session_attachment`/`require_session_attachment` | Publication follows association/adoption; failed adoption publishes nothing; direct sessions also associate. |
| Drain observer/cleanup/release flags | Idempotent release and LS-5. |
| Drain `unsubscribe_all` and raw unsubscribe/close/drop calls | High-level ordering plus structural proof that no drain path reaches observer release, dispatcher/session close, detail retirement, plan drop, or compensation. |
| Adapter domain teardown on shutdown | Adapter-local close marking, generation invalidation, drain supersession, and blocked-offer wake remain. |
| Service session receipt maps and plan mutation receipts | One application receipt suite covers six starts, mutation, replay/conflict, retirement, shutdown. |
| Service detail-owner parallel authority | Exact detail retained through dispatcher close and then retired. |
| Adapter task-capacity authority | Application refuses task 49 before factory/workflow/observer/dispatcher. |
| Any application delivery field | Adapter retains queue 64, backpressure, drain claim, generation, terminal-delivery fact, and response replay. |

LC-1a removes no adapter delivery shutdown. Provisional delivery state is
discarded by the adapter call frame on failure. No service/application rollback
points into the adapter.

LC-1a also adds a structural import/call-path rule: web drain may import task
views and the protocol only from `namisync.interfaces.task_port`; it may not
import `task_lifecycle`, `session_observer`, dispatcher, or raw service cleanup.
No drain-side path may reach observer release, dispatcher/session close, exact
detail retirement, plan drop, or compensation.

That strong indirect law deliberately retains the adapter-local
`namisync.interfaces.web._exception_graph` helper: 37 source lines duplicate
the 27-line exception-retirement mechanism. Injecting the callable would spread
a cleanup capability through seven constructors and contaminate the transport
codec. Reopen this decision if one additional interface consumer needs the
same mechanism; do not generalize it before that trigger.

### LC-1b whole-operation cleanup replay reduction

#### Objective and accepted shape

LC-1b removes the general-purpose application transaction interpreter that
LC-1a introduced for process-local cleanup. It keeps the LC-1a ownership
boundary and replaces step selection, acknowledgement, and marker repair with
two straight-line operations:

1. admission rollback ensures observer, exact detail, and exact unpublished
   association absence; and
2. session/task settlement ensures observer, Dispatcher custody, exact detail,
   optional exact plan, and then exact application association/task absence.

Each operation has one coarse, exact-token, whole-operation claim. A contender
for the same association waits for or joins that operation; a retry after
failure executes the whole fixed sequence again. The application may retain
the monotone settlement target (`session` or `task`), truthful terminal
digest, actual observer/detail/plan liabilities, and whether a whole operation
is in flight. It retains no physical-step progress. Session release may leave
the task and plan receipt alive; later task close escalates the target and
replays the full cleanup sequence before exact plan/task retirement.

#### Finite disappearance and positive-proof symmetry

The production disappearance domain is exactly
`namisync/interfaces/task_lifecycle.py` and
`namisync/interfaces/service.py`. The matching test-disposition domain is
exactly `tests/test_task_lifecycle.py` and `tests/test_service.py`.
Before production edit, record every AST reference in those four files to the
symbols and fields below. Each test becomes only `mechanism-removed`,
`reanchored-owner`, or `boundary-retained`; no unrelated test is merged or
compressed.

| Required disappearance | Required positive proof after removal |
| --- | --- |
| `LifecycleStep` and every string-dispatched cleanup-step branch | `test_lifecycle_cleanup_sequences_are_fixed_and_owner_idempotent` proves straight-line session cleanup and exact subjects; the reanchored LS-4a admission tests prove the separate rollback sequence. No owner returns a step description. |
| `SettlementReservation`, `reserve_settlement`, `activate_settlement`, and `abandon_settlement_reservation` | `test_lifecycle_whole_settlement_claim_excludes_reobserve_and_same_session_peer` proves exact sealing, reobservation exclusion, observation-end/abandon wakeup, and disjoint independence. `test_ls_4b_whole_operation_cleanup_singleflights_concurrent_callers` proves completion wakeup; `test_lifecycle_close_wakes_settlement_claim_waiter` proves close wakeup. |
| `settlement_step`, `complete_settlement_step`, and their service loop | The collective LS-4b pre/post owner-fault witnesses replay the whole sequence from current truth; the deterministic C1 test covers the two-caller race. They assert final owner truth and boundary effects, not a next-step cursor. |
| `admission_rollback_step`, `complete_admission_rollback_step`, `abandon_admission_rollback_step`, and `AdmissionRollbackClaim.step` | `test_ls_4a_admission_rollback_owner_fault_retries_from_observer`, the adoption-rejection/publication witnesses, and the two whole-rollback replay/single-flight tests cover exact unpublished attachment, detail, and observation liabilities. |
| `_SessionAssociation.admission_cursor`, `rollback_last_completed`, `settlement_cursor`, `settlement_reservation`, `settlement_last_completed`, and `settlement_last_finished` | `test_lifecycle_state_has_no_cleanup_step_or_marker_progress` rejects any aggregate attribute or module-owned dataclass field containing `cursor`, `marker`, `step`, `last_completed`, `progress`, or `reservation` without freezing unrelated imports or field sets. |
| `_SessionAssociation.observation_last_completed` and marker-repair double calls around observation completion | `test_observation_claim_retries_from_observer_truth_without_marker_history` proves claim identity, stale-end safety, and settlement after claim release without marker history. `test_cleanup_retry_uses_current_owner_truth_not_application_progress` proves cleanup replay derives release from current observer/owner truth. |
| `_admission_step_locked`, `_apply_admission_rollback_completion_locked`, `_settlement_step_locked`, `_apply_settlement_completion_locked`, and `_settlement_reservation_locked` | The collective LS-4a/LS-4b owner-fault tests cover observer, Dispatcher, detail, and plan failures before and after owner transitions. Each retry begins at observer release and derives the remaining work from current owner truth. |
| The immediate second-call repair branches around `complete_start`, `mark_published`, `complete_observation`, `complete_plan_retirement`, `complete_admission_rollback_step`, `complete_settlement_step`, and `finish_settlement` | Atomic start publication, observation truth, exact plan retirement, the collective LS-4 owner tests, and the frozen T1 plus retained adapter lost-response tests prove the surviving properties. Post-effect interruption may repeat cleanup calls while each observable cleanup effect and terminal delivery remains unique; each bridge retry receives its specified replay response. No test injects failure inside a pure-memory marker merely to require a second marker call. |

The old tests that assert a first-unfinished step, an exact marker replay, or an
unrepeated cleanup method invocation are removed with that mechanism. Tests of
receipt replay/retirement, terminal reconciliation, exact association,
observation exclusion, plan-token successor safety, task capacity, delivery
shutdown, bridge/CLI/events/persistence/filesystem boundaries, and Dispatcher
cleanup remain and are reanchored only as needed to the simpler owner.

#### Finite LS-4b fault and concurrency domain

Sequential fault injection is additive rather than Cartesian: each row proves
one owner's retry algebra, and one separate two-caller test proves the common
whole-operation exclusion. LC-1b does not claim exhaustion by sampling every
`step x interruption x peer` combination.

| Row | Fault seam | Required observation |
| --- | --- | --- |
| S1 | Observer release raises before retirement | The association stays sealed; retry starts at observer release and reaches full absence. |
| S2 | Observer release retires the subscription, then raises | Retry calls release again; callback/stream/thread retirement and terminal delivery remain unique. |
| S3 | Dispatcher close raises before custody close | Retry calls exact-session close again; no later owner runs before custody is absent. |
| S4 | Dispatcher custody closes, then the caller observes failure | Retry reaches `SessionNotFound`; only the sealed exact application settlement treats it as already absent, and Dispatcher remains strict elsewhere. |
| S5 | Exact detail retirement raises before or after its owner-locked removal | Retry calls exact detail retirement again; only the admitted detail is absent and no successor is touched. |
| S6 | Exact plan retirement raises before or after runtime removal | The retirement barrier remains; retry removes only the same `PlanToken`'s runtime, selection, receipt, and application state, never a successor. |
| S7 | Application finalization is not observed by the caller | Exact-token retry returns or converges on the same released/retired logical state without another domain effect; a new command invocation receives only its existing identical replay response. |
| C1 | Two same-association callers overlap at a barrier | Exactly one whole cleanup operation is active; the peer joins or retries after it. Invocation counts may exceed one across retries, but every owner transition and boundary effect occurs at most once. |
| C2 | Two disjoint associations settle at barriers | Both enter lower owner work concurrently; the coarse claim introduces no global lifecycle serialization. |

The harness may inject failure immediately before or after an owner call. It
does not monkeypatch `Condition.notify_all`, individual field assignments, or
other bytecodes inside a locked pure-memory transition and then treat that
synthetic exception point as a supported collaborator boundary. Lifecycle
critical sections remain small, non-blocking, and retry-derived from retained
owner identities. Notification is not durable evidence.

#### Non-goals

- No change to LC-1a ownership, task-port surface, receipt keys/lifetimes,
  48-count bounds, task-id minting, terminal reconciliation, exact association,
  or plan mutation/retirement exclusion.
- No bridge, CLI callback, event, persistence, filesystem, adapter replay,
  queue/drain/generation, backpressure, or shutdown-delivery change.
- No observer move or subscription redesign; that remains LC-2.
- No change to Dispatcher public semantics, close implementation,
  `_AdmissionCleanup`, scheduling, custody, concurrency, or admission.
- No LC-3 record composition and no LC-4 dispatcher-entry experiment.
- No replacement transaction, workflow, effect, journal, reducer, saga,
  generic idempotency, or cleanup framework.
- No opportunistic bug hunt, test compression, or unrelated cleanup.

#### Acceptance, verification, and commit gate

- Every disappearance row is absent and has its named positive proof.
- Task lifecycle retains one domain-effect receipt authority, one exact
  association authority, one plan retirement exclusion, and at most one coarse
  admission-rollback claim plus one coarse settlement claim per association.
- Neither lifecycle nor service retains a cleanup step name, physical-step
  cursor, completed-step set, last-completed/last-finished marker, or
  collaborator rollback callback.
- Repeated cleanup calls are accepted; repeated or missing observable effects,
  wrong-subject cleanup, false terminal reconciliation, and receipt replay
  drift remain failures.
- The diff from the LC-1a closing commit is net-subtractive across the two
  production files, with no new generic abstraction. Line counts are reported
  evidence, not an independent stop or permission to weaken tests.
- T1 is unchanged; enduring LS-1/LS-2/LS-3/LS-4a/LS-4b/LS-5 pass; focused
  lifecycle, service, bridge-service, and affected interface tests pass; the
  ordinary suite and all import contracts pass.

Run:

```powershell
rg -n "LifecycleStep|SettlementReservation|admission_cursor|rollback_last_completed|observation_last_completed|settlement_cursor|settlement_reservation|settlement_last_completed|settlement_last_finished|admission_rollback_step|complete_admission_rollback_step|abandon_admission_rollback_step|reserve_settlement|activate_settlement|abandon_settlement_reservation|settlement_step|complete_settlement_step|_admission_step_locked|_apply_admission_rollback_completion_locked|_settlement_step_locked|_apply_settlement_completion_locked|_settlement_reservation_locked" namisync\interfaces\task_lifecycle.py namisync\interfaces\service.py
.\.venv\Scripts\python.exe -m pytest -q tests\test_task_lifecycle.py tests\test_service.py tests\test_bridge_service.py
.\.venv\Scripts\python.exe tools\task_lifecycle_audit.py verify --baseline tools\task_lifecycle_baseline.json --output "$env:TEMP\task-lifecycle-lc1b.json"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\lint-imports.exe
```

The first command's terminal observation is no match. Before commit, update
`ARCHITECTURE.md`, `INTERFACES.md`, `DEFENSE.md`, this document, the test
ledger, changelog, and handoff to the implemented contract and exact evidence.
After the mergeable LC-1b commit passes its full gate, stop for user recap and
review; do not begin LC-2.

Commit gate: `refactor(interfaces): simplify lifecycle cleanup replay`.

### LC-2 observation lifetime consolidation

#### Objective

Make observer ownership mechanically complete without changing push delivery,
recovery, cancellation responsiveness, adapter backpressure, or application
cleanup replay.

#### Scope and approach

- Move the observer implementation from `service.py` to
  `session_observer.py`.
- Replace `_Observation` and returned rollback closures with private
  `SessionSubscription`.
- Keep observer operations `observe`, `adopt`, `reobserve`, `release`, `wait`,
  and `close`. Preserve the public service-facing `observe`, `reobserve`,
  `unsubscribe`, and `wait` surface; `unsubscribe` delegates to observer
  `release`.
- `release(session_id)` is idempotent and solely owns stop, stream close,
  callback/thread completion, join, and subscription retirement. An external
  release returns only after worker retirement. Callback self-release removes
  the subscription atomically, prevents a later stream/worker from using that
  identity, skips self-join, and lets that worker finish under the unchanged
  current-delivery behavior as its callback unwinds. The observer retains that
  retiring physical subscription until unwind so a concurrent external
  release can still wait for it. A retry may repeat the release call but may
  not repeat an observable transition.
- `adopt` closes a rejected stream itself and returns no cleanup or rollback
  authority.
- Keep only the exact session association and observer liability needed to
  request release in application state. `TaskLifecycle` records no observer
  stream, sink, subscription, thread, callback, stop/done state, release
  cursor, completed-step marker, or physical-release progress. Whole-operation
  cleanup replay derives completion from current observer truth.
- Preserve shutdown order: the adapter first marks delivery closed,
  invalidates generations, supersedes drains, and wakes blocked offers; the
  service observer then releases subscriptions; Dispatcher/service shutdown
  follows.
- Extend the strong import contract so `namisync.interfaces.web.drain` cannot
  import or indirectly reach `session_observer`, in addition to Dispatcher,
  service, and `task_lifecycle`. No drain-side path may release observation or
  close session custody.
- Retain the forced adapter-local
  `namisync.interfaces.web._exception_graph.retire_exception_graph` duplicate.
  LC-2 does not weaken the drain import contract, inject a cleanup callable
  through transport constructors, move the helper into `task_port`, or
  otherwise consolidate it. Its existing one-additional-interface-consumer
  reopening trigger remains unchanged.

#### Acceptance criteria

- `SessionObserver` is the only retained production owner of an adopted
  observation stream, sink, subscription, observer thread, stop, and done
  state. Dispatcher creates and custodies subscriber streams; the service
  admission call frame may only transfer an offered stream to the observer or
  close an offer that will not be adopted.
- Application lifecycle and adapters retain no observer resource or cleanup
  capability. Application replay may request exact-session release again but
  cannot select or acknowledge an observer-internal step.
- Reobserve fully releases the old subscription before installing its
  replacement; a stale release cannot close the replacement stream.
- A terminal snapshot installs no new subscription.
- Callback self-release, sink failure, stream-close failure, join timeout, and
  service-close retry remain truthful and deadlock-free.
- `test_disc_b1_blocked_cli_callback_preserves_cancel_responsiveness` retains
  the baseline callback/control/terminal ordering without converting the CLI
  push callback into a pull loop or inserting another queue.
- `test_disc_b2_adapter_shutdown_wakes_offer_before_service_observer_release`
  retains
  adapter delivery withdrawal, blocked-offer wake, handler departure, and
  eventual observer release while the physical subscription owner moves.
- The web-drain import contract forbids `session_observer`, and structural
  searches find no adapter call path to observer release or session close.
- T1 and the enduring LS-1 through LS-5 detectors remain unchanged.

#### Regression watchlist

- A blocked callback delaying cancellation, delivery withdrawal, or shutdown.
- External release reporting success before callback/thread retirement, or
  callback self-release claiming that its currently executing frame has
  already unwound.
- Reobserve leaving both streams active or a stale release closing the
  replacement.
- A callback self-release deadlock or a join timeout reported as successful
  retirement.
- A CLI pull loop, new queue, changed callback timing, or changed 128/64/64
  capacity/backpressure behavior.
- Observer acquisition of task, receipt, settlement, Dispatcher-custody, or
  delivery semantics.
- Observer-release progress or rollback capability reappearing in
  `TaskLifecycle` under another name.
- Import-law relaxation or a new generic helper introduced to deduplicate the
  forced web exception-retirement mechanism.

#### Tests and evidence

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_service.py tests\test_cli.py tests\test_task_lifecycle.py tests\interfaces\web\test_host.py
.\.venv\Scripts\python.exe -m pytest -q --dept interfaces --dept dispatcher
.\.venv\Scripts\python.exe tools\task_lifecycle_audit.py verify --baseline tools\task_lifecycle_baseline.json --output "$env:TEMP\task-lifecycle-lc2.json"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\lint-imports.exe
```

Pass observation includes barrier transition logs proving control advances
independently of the blocked CLI callback and observer release completes after
adapter delivery withdrawal. The frozen T1 artifact matches without
refreezing, every enduring detector passes, all import contracts remain kept,
and the ordinary suite is green.

#### Documentation and handoff

Update observer lifetime and shutdown ordering in `INTERFACES.md`, update the
contract-to-source locator in `ARCHITECTURE.md`, record exact evidence here,
and replace `HANDOFF.md` with the resulting checkpoint state. Update
`CHANGELOG.md` when the checkpoint closes.

#### Adversarial review

Search for retained rollback closures; stream, sink, subscription, or thread
references outside observer code; task/receipt/settlement semantics inside the
observer; observer progress inside application lifecycle; adapter calls to
observer/session cleanup primitives; and an import-law exception introduced to
reach either observer code or the shared exception-retirement helper. Review
release/reobserve identity checks, callback self-release, failure truth, and
shutdown ordering separately from green-suite status.

#### Commit gate

`refactor(interfaces): consolidate session observation lifetime`

### LC-3 accepted structural tradeoff

`StoredSessionRecord` becomes the canonical frozen/slotted value and live
`SessionRecord` composes it plus checkpoint. Preserve the positional/keyword
constructor and `inspect.signature(SessionRecord)`, frozen/slotted behavior,
read-only named access, equality, result/resources identity, persisted bytes,
and public behavior. After a finite repository search, explicitly accept
changes to `dataclasses.fields`, `replace`, `asdict`, `astuple`, repr, pattern
matching/`__match_args__`, `__annotations__`, `__dataclass_fields__`, the exact
hash tuple's nesting, and slotted pickle/copy state. Dispatcher replaces the
contained stored value. No `__getattr__`, generated descriptor, generic record
framework, projection helper, or live backreference may be introduced.

### LC-4 accepted result and finite probe

Production keeps the parallel maps. Scratch `_SessionEntry` is frozen, slotted,
behaviorless, and excludes global scheduler state and unpublished-admission
cleanup. The only declared mutators are
`_install_session_entry_locked`, `_replace_session_entry_locked`,
`_mark_session_cleanup_locked`, and `_drop_session_entry_locked`. AST checks
cover assignments/deletions and every mutating method/alias in their finite
domain. A scratch instrumented-condition check must observe lock ownership at
every mutator. If that needs a production helper, wider scope, or control-flow
change, record a negative result. Positive or negative closes LC-4; mutation
concentration alone never proves lock safety. Reverse all scratch code.

### LC-5 exact twelve-file domain

Production owners:

1. `namisync/core/session.py`
2. `namisync/core/events.py`
3. `namisync/core/event_v5.py`
4. `namisync/workflows/views.py`
5. `namisync/interfaces/web/assets/bridge.js`
6. `namisync/interfaces/web/bridge.py`

Test/witness owners:

1. `tests/core/test_session_events.py`
2. `tests/core/test_event_v5_consumers.py`
3. `tests/test_bridge_resume.py`
4. `tests/test_cli.py`
5. `tests/interfaces/web/_public_view_witnesses.py`
6. `tests/interfaces/web/test_browser_event_v5_consumers.py`

Those twelve are the entire `git diff --name-only` domain. Twelve is derived
from the default-null serializer and real non-null JavaScript validation path,
not an independent complexity threshold. A thirteenth file or lifecycle-
specific field logic fails the disposable probe. Default-null bytes remain
unchanged; all scratch changes reverse and `rg simplification_probe` ends empty.

### LC-6 exact retirement and retained cost

LC-6 removes only the three temporary T1 artifacts and the single matching
`tools` department entry named in LC-0a. The enduring stop detectors,
observation barriers, positive-owner tests, `tests/test_task_lifecycle.py`, and
its `interfaces` department entry remain. LC-6 retired exactly 1,667 temporary
lines: 905 runner, 601 baseline, and 161 self-test lines.
`tests/test_task_lifecycle.py` remains as 2,012 lines of enduring owner and
stop-class coverage. Only the deleted audit test's `tools` entry retired.
Wholesale retained-test teardown remains outside this register.

## 6. Evidence and resumption

| Evidence | Result |
| --- | --- |
| Base | LC-0 began from clean `milestone1-anthony` at `5631066`; the fresh LC-1a rebuild begins from corrected selection-race commit `c456cf4`. Prior recovery commits remain isolated and are not review units. |
| Register refinement | User-adjudicated refinements incorporated 2026-09-02. LC-0a closes four nonblocking guard findings; LC-0b corrects LS-1. This repository document is now the sole maintained plan, and the `.codex` snapshot is intentionally left unchanged. |
| T1 stability (retired) | Three fresh processes and the frozen baseline were byte-identical: SHA-256 `AC08426E682BC362CC9E0CAB9A7ABE4FA998518DC5E9CCFD3FB0DF86F68CB53B`. The oracle rejected bridge, CLI, event-sequence, fixed drain-identity, persistence, and filesystem corruptions. LC-6 matched this hash once more before retirement. |
| `DISC-B1` | With the CLI push callback blocked after `PhaseChanged`, cancellation is accepted and dispatcher truth reaches canceled before callback release; release then yields one Terminal, one terminal record, canceled exit mapping, exact stdout, and exact stderr. |
| `DISC-B2` | `begin_close` marked delivery closing, incremented its generation, and woke the blocked bounded offer before the then-current `unsubscribe_all`; the baseline then released the observer once and ordered offer withdrawal, adapter unsubscribe, session close, and service close. This recorded baseline behavior, not target ownership. |
| T2 baseline | LS-1, LS-2, LS-4a, and LS-5 pass untouched production. The old LS-1 assertion intermittently rejected `[1, 2, 3, Gap@68(first_missed=4), Gap@4(first_missed=4), 141, ...]`; the finite normative audit established that this is permitted recovery rewind, not evidence of LS-1 loss or duplication. The corrected module is `19 passed`; its final barrier-forced LS-1 path is 30/30 across fresh processes, and deliberate duplicate/unannounced-loss corruptions fail. LS-3/LS-4b remain introduced LC-1a guarantees. |
| Test census | The ledger began with 131 behavioral and eight helper rows over the exact seven-file corpus. LC-6 adds six deleted-oracle test dispositions and one helper-group disposition, for 137 behavioral and nine helper rows; the finite LC-1b crosswalk remains separately counted. Every row is closed, zero pending fields remain, every current-owner proof resolves, removed-mechanism tests/helpers are absent, and retained helpers have live dependents. |
| Broad baseline | LC-0b ordinary suite with required bundled Node: `4909 passed, 4 skipped, 28 deselected`; import law: 11 kept, 0 broken. An initial run without required Node had only the five expected runtime-availability failures and was rerun with the bundled executable. |
| Adversarial review | A separate read-only review found five guard defects; all were corrected and independently re-reviewed closed. No production file or lifecycle behavior changed. |
| LC-0a amendment | Ordered `[A, B, A, B]` normalization and fixed-ID preservation are explicit; runner/baseline format remain literal 1; frozen SHA-256 remains `AC08426E682BC362CC9E0CAB9A7ABE4FA998518DC5E9CCFD3FB0DF86F68CB53B`; oracle plus department checks are `27 passed`; the diff contains only this register and the oracle self-test. |
| LC-0b amendment | No normative global raw-Gap monotonicity clause exists; existing required browser witnesses intentionally repeat a synthetic Gap sequence. The corrected LS-1 detector uses explicit ejection/recovery/terminal barriers and finite missing-reliable intervals. T1 still matches, production and `event_bus.py` are unchanged, and the unsupported `BUGS.md` entry is removed rather than marked fixed. |
| Pre-LC-1a selection fix | `test_selection_mutation_drop_race_does_not_retain_or_replay` pauses after the initial successful plan read, completes `drop_plan`, then resumes. The old tree returned `KeyError` but retained mutated selection state and its receipt; the fixed tree returns the same `KeyError` with zero effect, no retained state or receipt, and identical-command retry also raises without effect or replay. A distinct A→B→C→D identity witness proves stale retry truth never overwrites a concurrent successor; both witnesses passed in 30 fresh processes. The separate fix commit `fix(interfaces): close plan selection retirement race` is based exactly on `2ad8e35`; service/bridge is 132 passed, ordinary is 4,911 passed/4 skipped/28 deselected with bundled Node, T1 matches, and import law is 11 kept/0 broken. |
| LC-1a authority result | `TaskLifecycle` is the sole domain-effect receipt, task/session association, admission rollback, and logical-settlement owner. `TaskLifecyclePort` exposes only task start, exact reobservation, terminal release, and task close. Web drain retains bounded response replay, provisional delivery, queue/drain/generation state, terminal-delivery facts, and shutdown wakeup, with no raw domain cleanup path. |
| LC-1a focused verification | Lifecycle guards: 38 passed; rebuilt bridge/service boundary: 28 passed; drain/commands/host: 369 passed; bundled-Node transport: 124 passed. Introduced LS-3 and LS-4b, exact admission rollback, task capacity, response replay, close/release convergence, and delivery-shutdown witnesses pass. |
| LC-1a department verification | Bundled-Node department run: 2,339 passed, 2,645 deselected in 83.84 seconds, after reanchoring the sole stale synthetic service fixture. |
| LC-1a boundary and structure | The frozen T1 output matches baseline without refreezing. All 12 import contracts pass, including the strong indirect drain prohibition. The retained 37-line adapter helper duplicates 27 mechanism lines and has the one-more-interface-consumer reopening trigger stated above. |
| LC-1a ordinary verification | Bundled-Node ordinary suite: 4,952 passed, four skipped, 28 deselected in 232.55 seconds; exit 0. LC-1a is complete and LC-2 remains paused for review. |
| LC-1b amendment | User-authorized reduction companion to LC-1a. The accepted retry unit is now the whole cleanup operation; repeated exact-subject cleanup calls are permitted while repeated observable effects remain forbidden. The finite disappearance, LS-4b fault/concurrency, non-goal, verification, and pause domains above are the implementation denominator. No production or test result is claimed by this amendment. |
| LC-1b reduction | Removed application cleanup steps, cursors, per-step acknowledgements, marker-repair calls, and the service step interpreter. The two production files are net 440 lines smaller; the two lifecycle/service test modules plus bridge fixture are net 74 lines smaller. The 22 renamed/removed tests have closed dispositions, all replacement names resolve, and no boundary test changed. |
| LC-1b verification | Focused lifecycle/service/bridge: 176 passed. Bundled-Node interfaces/workflows/dispatcher neighborhood: 2,328 passed and 2,645 deselected. Frozen T1 matches without refreezing; import law is 12 kept/0 broken; ordinary is 4,941 passed, four skipped, and 28 deselected in 220.72 seconds. The bounded independent reviews found one introduced admission-waiter shutdown defect, fixed before commit, and no remaining production or test finding. |
| Pre-LC-2 stabilization | Without adding a register row, one separate mergeable amendment replaces the brittle exact lifecycle-state snapshot with two negative structural guards, consolidates plan retirement to one tolerant exact-token acquisition, aligns exact plan-selection retirement, states whole-operation owner idempotency, disambiguates the rollback concurrency test name, restores this document's detailed LC-2 contract from the historical `.codex` snapshot, and reanchors every active ledger proof. Focused lifecycle/service/bridge: 179 passed; frozen T1 matches; import law: 12 kept, 0 broken; ordinary with bundled Node: 4,944 passed, four skipped, 28 deselected in 214.64 seconds. |
| LC-2 observation ownership | `SessionObserver` and private `SessionSubscription` moved to `interfaces/session_observer.py`; `adopt` returns no rollback capability, `release` is the one physical teardown operation, and service/application state retains only session association. Callback self-release keeps its exact physical subscription observer-owned until unwind, so a concurrent external release can join it; the baseline terminal event-plus-record callback pair remains unchanged. The strong indirect drain prohibition now includes the observer module. The production move is net 56 lines because this self-release custody is explicit; no cursor, application progress, adapter cleanup capability, or second delivery queue was added. |
| LC-2 verification | Focused observer/CLI/lifecycle/host: 298 passed; interfaces/dispatcher departments with bundled Node: 1,583 passed and 3,390 deselected; bridge/drain: 136 passed; observer fault slice: 54 passed. Frozen T1 matches without refreezing; import law is 12 kept/0 broken; ordinary is 4,941 passed, four skipped, and 28 deselected in 213.01 seconds. Five obsolete returned-rollback parameter cases were removed and two owner-level tests added; every changed test has a closed ledger disposition. Two independent reviews found the self-release external-join gap in the draft, verified its owner-local fix, and reported no remaining blocker. |
| LC-3 record composition | `StoredSessionRecord` is now the one metadata/result value and validator; live `SessionRecord` contains that exact value plus its checkpoint and preserves the old public constructor and named read-only access. Dispatcher constructs one pair at admission, replaces only the stored value for metadata/result transitions, reuses it for checkpoint-only changes, and passes the contained object directly to the store. The finite 13-file consumer audit found no live-record use of generic dataclass projection/replacement, pattern matching, copy, or pickle. The registered introspection changes are accepted. This removes the ten-field dispatcher projection and duplicate validation; explicit compatibility properties make the two production files net 48 lines larger, without a new framework or retained graph. |
| LC-3 verification | Core/dispatcher focus: 391 passed; the complete core session/event file after the final validation witness: 237 passed; core/dispatcher departments with bundled Node: 1,368 passed, one skipped, and 3,605 deselected. Frozen T1, including persisted bytes and public records, matches without refreezing; import law is 12 kept/0 broken; ordinary is 4,943 passed, four skipped, and 28 deselected in 212.16 seconds. Two bounded reviews found no blocker, missed consumer, lock/scheduler edit, or persistence identity drift. |
| LC-4 entry feasibility | The current denominator is seven entry-local session containers, not the historical nine. A disposable frozen/slotted/behaviorless `_SessionEntry` consolidated those seven while leaving pending order, reservations, leases, workers, current/retiring generations, fairness, and failed-admission cleanup global. Four declared mutators covered every `_sessions` identity write. A finite AST gate rejected other writes, entry-field mutation, and ordinary aliases; a test-only mapping observed the actual write caller and `Condition._is_owned()` and rejected a deliberate unlocked write. This proves the exercised mapping writes were condition-owned, not that the shallow aggregate graph or future call sites are lock-safe. |
| LC-4 result and reversal | The prototype was mechanically feasible but failed the value test. It rewrote 78 reads and 27 mutation statements, grew dispatcher production by 101 net lines (`+202/-101`), required a 321-line scratch gate plus temporary reanchoring of 15 private-map tests, and initially retained a closed checkpoint through a scheduler-frame aggregate local. Clearing that local restored the retention witness, but demonstrated relocated risk. Scratch probes were 2 passed, the named concurrency slice 7 passed, and the fully reanchored dispatcher department 157 passed/4,820 deselected. Independent review found no reason to claim stronger lock safety. All four scratch paths were reversed, `git diff --exit-code` and final `_SessionEntry` searches were empty, and the disposable branch was deleted. Production retains the parallel maps. |
| LC-5 terminal-field probe | The scratch `OperationResult.simplification_probe` crossed equality, snapshotting, terminal summary/event encode and decode, exact stored/live identity, dispatcher/store terminal truth, public result/record/task-drain views, the unchanged CLI push callback, Python bridge serialization, and real JavaScript validation. Default-null event and bridge fields remained absent. The raw `git diff --name-only` set was exactly the six production plus six test/witness paths declared above; the scratch was `+438/-27`. No lifecycle, observer, dispatcher, drain, database, schema/version, compatibility, or generic-helper path changed. This passes the derived twelve-file scope gate; twelve is evidence of the required path, not a separate threshold. |
| LC-5 verification and reversal | The complete declared executable test set passed 941 tests with bundled Node; the strengthened CLI, real-browser record, and complete bridge public-view witness slice passed 52 tests. Frozen T1 matched, `git diff --check` had no patch error, and two independent reviews found no blocker. Every scratch change was restored to `67ffe3c`; final `rg simplification_probe`, staged/unstaged diffs, and status were empty, and `codex/task-terminal-field-probe` was deleted. |
| LC-6 final T1 and retirement | The last capture matched frozen SHA-256 `AC08426E682BC362CC9E0CAB9A7ABE4FA998518DC5E9CCFD3FB0DF86F68CB53B`. LC-6 then deleted only the 905-line runner, 601-line baseline, 161-line self-test, and the self-test's `tools` department entry. The department-manifest check passed 16 tests. |
| LC-6 test disposition | Six deleted audit test definitions and one helper group are closed in `TASK_LIFECYCLE_TEST_LEDGER.md`: the boundary capture is reanchored to the enduring public set; five tests and the helper group retired with the temporary mechanism. Exact searches found zero orphan imports, fixtures, helpers, or external dependents. The 2,012-line enduring lifecycle module and its `interfaces` entry remain. |
| LC-6 integration verification | The enduring public/T2 replacement set passed 32 tests; core/workflows/dispatcher/interfaces departments passed 3,542 with one skip and 1,421 deselected; ordinary passed 4,932 with four capability skips and 28 headed deselections; all 12 import contracts held. The reanchored transport module excluding the independent off-origin accessibility node passed 34 tests; that node remained unverified because its Windows UI Automation probe twice raised `ElementNotAvailableException`. No product, bridge-security, or lifecycle code was changed to mask that host-capability failure. |
| LC-6 ownership and complexity audit | In the predeclared ten-path production slice compared from `c456cf4` through the lifecycle series, production is net `+1,311` lines (`+2,959/-1,648`). The result is authority consolidation, not source-line reduction: `TaskLifecycle` is the one census-scoped domain-effect receipt/association/settlement owner, `SessionObserver` is the one subscription owner, Dispatcher alone owns custody, and drain has only the four high-level port calls with no raw cleanup path. No relocated receipt, association, observer, compensation, or drain-cleanup authority was found. |

- **Current checkpoint:** LC-6 complete; this register is closed.
- **Next action:** review the atomic closeout. Any further lifecycle or
  retained-test consolidation requires separately adjudicated scope.
- **Recovery rule:** do not merge or cherry-pick `59affc4`, `dc94aef`, or
  `codex/wip-20260902-2029-task-lifecycle-lc1a`; those recovery snapshots
  remain isolated and are not review units.
- **Closed evidence limitation:** the off-origin native headed node could not
  obtain its accessibility text from this Windows session because UI Automation
  reported a vanished element. The other 34 transport-module nodes pass;
  this register neither repairs nor suppresses the independent probe.
- **Resolved guard stop (2026-09-02):** the observed recovery rewind violated
  only an unsupported detector assertion. It did not establish the stated
  LS-1 consequence, so no product defect or production fix is authorized. The
  deterministic replacement closes the guard issue and permits LC-1a recovery.
