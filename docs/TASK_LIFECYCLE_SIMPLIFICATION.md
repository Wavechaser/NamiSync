# Task Lifecycle Machinery Simplification

**Standing (2026-09-02): active closed register; LC-0 complete and paused for
review.** This
document owns the repository delivery denominator, stop rules, guard evidence,
and resumption state for the task-lifecycle simplification. Findings are output,
not implicit implementation scope. Only explicit user adjudication may alter
this register after implementation begins.

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
Application state retains only association and settlement progress, never an
`EventStream`, sink, observer thread, or observer rollback callback.

Normal release is:

`adapter delivery fact -> application settlement -> observer release confirmed -> dispatcher close -> detail retirement -> optional plan/task retirement`

A logical settlement may retry its first unfinished physical step; a completed
step never repeats.

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
  closed root `SIMPLIFICATION.md` register.

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
| `LS-1` silent loss/duplicate | **Baseline, LC-0.** `test_ls_1_delivery_has_no_silent_loss_or_duplicate` reconciles non-`Gap` delivery with producer sequence, exact `Gap` coverage, unique sequence/terminal, and terminal-last. |
| `LS-2` wrong/unreachable session control | **Baseline, LC-0.** `test_ls_2_session_control_reaches_only_corresponding_dispatcher_record` proves service `pause`/`resume`/`cancel` mutate only the exact dispatcher record; unknown or retired sessions mutate none. |
| `LS-3` false terminal reconciliation | **Introduced, LC-1a.** `test_ls_3_terminal_reconciliation_matches_dispatcher_truth` compares delivered Terminal/record with dispatcher truth before settlement; injected disagreement prevents close and success replay. An injected internal disagreement alone is not a baseline defect; an actual supported baseline disagreement is. |
| `LS-4a` missing/duplicate admission rollback | **Baseline, LC-0.** `test_ls_4a_submit_session_rollback_converges` closes over the finite F1-F5/R1-R4 application-admission table and D1-D4 dispatcher cleanup table below. It records exact attempts and successful state transitions: each physical transition succeeds once, while the baseline may make an idempotent follow-up call. |
| `LS-4b` missing/duplicate application settlement | **Introduced, LC-1a.** `test_ls_4b_application_settlement_retries_only_unfinished_step` faults observer release, dispatcher close, exact detail retirement, and plan retirement once under one two-caller race; only the unfinished step retries. Delivery-factory failure is a separate zero-application-compensation row. |
| `LS-5` retained stream/callback | **Baseline, LC-0.** `test_ls_5_release_retires_stream_and_callback` proves observer lookup and subscriber custody disappear, callback count cannot advance, and a weak sink owner is collectible. |

LS-4a is a pre-migration characterization of the machinery LC-1a removes. It
is dispositioned and removed only after LS-4b passes at the new owner. The
enduring stop-detector set after LC-1a is LS-1, LS-2, LS-3, LS-4b, and LS-5.

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

### T1 temporary corpus

`tools/task_lifecycle_audit.py`, `tools/task_lifecycle_baseline.json`, and
`tests/test_task_lifecycle_audit.py` use production bridge dispatch, real
service/dispatcher/observer/task-drain composition, and a real plan-only
filesystem fixture. They capture:

- canonical envelopes for all four commands and identical replay of start,
  terminal release, and task close;
- every delivered update/terminal record for one complete plan session,
  including exact order/body/`Gap`/terminal-last;
- a fixed declined-plan CLI stdout, exact stderr, and exit;
- before/after source/target manifests with file size, SHA-256, and mtime;
- existence and SHA-256 for ledger/history main files and sidecars.

The committed corpus uses one fixed canonical fixture root and injects a fixed
1 TiB free-space result into the declined-plan CLI fixture. Those are declared
fixture inputs, not normalization. Normalize only temporary roots, the three
explicit IDs returned by the production start as generated opaque identities,
and timestamps by stable occurrence identity. Fixture-owned request/drain IDs
and unrelated 32-hex text stay exact. Never normalize event bodies/order,
errors, dispositions, CLI
prose/exits, contents, persisted hashes, or repeated-id relationships.
Self-tests corrupt each boundary family. Three fresh-process captures must
normalize identically. Freeze once; delete only in LC-6.

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

`docs/TASK_LIFECYCLE_TEST_LEDGER.md` is the finite pre-implementation census.
Its AST/name/string procedure closes over exactly seven files and records 129
behavioral tests plus eight shared helpers. Each changed test is exactly
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
| `LC-1a` | Application becomes sole domain-effect owner; duplicate association/compensation/cleanup authority disappears; bounded adapter response replay and delivery shutdown remain. | `LC-0` | T1 unchanged; disappearance/test symmetry; structural no-drain-cleanup proof; introduced LS-3 and LS-4b plus enduring T2; affected neighborhood. | Pending |
| `LC-2` | Observer/`SessionSubscription` solely owns physical observation lifetime without CLI/web timing change. | `LC-1a` | Barrier timing, observer fault matrix, T1/T2, interfaces. | Pending |
| `LC-3` | Compose live/stored session records without lock, concurrency, persistence, or public behavior change. | `LC-0` only; independent of `LC-2` | Core/dispatcher, exact stored projection, T1 persisted bytes. | Pending |
| `LC-4` | Retain parallel maps and close disposable entry feasibility probe with truthful lock-ownership result. | `LC-3` | Scratch entry, finite mutators, AST plus instrumented condition, concurrency, full reversal. | Pending |
| `LC-5` | Run/reverse terminal-field probe inside exact derived twelve-file domain. | `LC-1a`, `LC-2`, `LC-3` | Exact diff, field-flow tests, no residual. | Pending |
| `LC-6` | Integrate/adversarially close and retire only temporary T1. | `LC-1a`-`LC-5` | Final T1 match; enduring tests; ordinary/headed/import/docs/cleanliness. | Pending |

### LC-1a mandatory disappearance and positive proof

| Disappearance | New-owner proof |
| --- | --- |
| `_StartEntry` domain-effect receipt/single-flight authority | Application replays identical resolved intent and rejects conflict; adapter cache retains only the permitted response fields. |
| `_TaskReservation.attached_session_id` authority | Exact lifecycle association for reobserve, terminal release, and task close; correct/wrong/retired identities. |
| Drain `_Compensation` | LS-4b exact-once settlement at the application owner; LS-4a is then dispositioned as removed-mechanism characterization. |
| Drain `_TaskCleanup`/progress booleans | Settlement retries only its first unfinished physical step. |
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

## 6. Evidence and resumption

| Evidence | Result |
| --- | --- |
| Base | Clean `milestone1-anthony` at `5631066`; prior recovery commit `59affc4` remains isolated and is not a review unit. |
| Register refinement | User-adjudicated refinements incorporated 2026-09-02; saved `.codex` plan also updated. |
| T1 stability | Three fresh processes and the frozen baseline are byte-identical: SHA-256 `AC08426E682BC362CC9E0CAB9A7ABE4FA998518DC5E9CCFD3FB0DF86F68CB53B`. The oracle rejects bridge, CLI, event-sequence, fixed drain-identity, persistence, and filesystem corruptions. |
| `DISC-B1` | With the CLI push callback blocked after `PhaseChanged`, cancellation is accepted and dispatcher truth reaches canceled before callback release; release then yields one Terminal, one terminal record, canceled exit mapping, exact stdout, and exact stderr. |
| `DISC-B2` | `begin_close` marks delivery closing, increments its generation, and wakes the blocked bounded offer before current `unsubscribe_all`; the baseline then releases the observer once and orders offer withdrawal, adapter unsubscribe, session close, and service close. This records current behavior, not target ownership. |
| T2 baseline | LS-1, LS-2, LS-4a, and LS-5 pass on untouched production. LS-4a covers F1-F5, R1-R4, and D1-D4; the full focused LC-0 set is `28 passed`. LS-3/LS-4b remain absent until LC-1a. |
| Test census | `docs/TASK_LIFECYCLE_TEST_LEDGER.md` contains 129 unique behavioral rows and eight unique helper rows over the exact seven-file corpus; all dispositions remain pending. |
| Broad baseline | Ordinary suite with required bundled Node: `4907 passed, 4 skipped, 28 deselected`; import law: 11 kept, 0 broken. |
| Adversarial review | A separate read-only review found five guard defects; all were corrected and independently re-reviewed closed. No production file or lifecycle behavior changed. |

- **Current checkpoint:** LC-0 complete; implementation is paused for user
  review. LC-1a has not started.
- **Next action after review:** begin LC-1a only if the guard/register outcome is
  accepted; first assign factual dispositions as old-owner tests change.
- **Recovery rule:** do not merge or cherry-pick `59affc4`; rebuild LC-0 as one
  coherent guard-only commit. The recovery snapshot remains isolated.
- **Stop:** any supported baseline defect, real-boundary drift, baseline LS
  consequence, nondeterministic T1, repeated-defect threshold, inability to
  preserve work, or required event/capacity change.
