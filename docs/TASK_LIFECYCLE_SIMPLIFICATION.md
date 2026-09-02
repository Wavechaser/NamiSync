# Task Lifecycle Machinery Simplification

**Standing (2026-09-02): active closed register; LC-0b complete and LC-1a
pending path-by-path recovery.** This
document owns the repository delivery denominator, stop rules, guard evidence,
and resumption state for the task-lifecycle simplification. Findings are output,
not implicit implementation scope. Only explicit user adjudication may alter
this register after implementation begins.

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
| `LS-1` silent loss/duplicate | **Baseline, corrected in LC-0b.** `test_ls_1_delivery_has_no_silent_loss_or_duplicate` barrier-forces ejection and recovery, maps every delivered reliable producer event exactly and at most once, requires every missing reliable producer sequence to fall within a finite interval announced by a delivered `Gap`, and checks terminal uniqueness/last separately. |
| `LS-2` wrong/unreachable session control | **Baseline, LC-0.** `test_ls_2_session_control_reaches_only_corresponding_dispatcher_record` proves service `pause`/`resume`/`cancel` mutate only the exact dispatcher record; unknown or retired sessions mutate none. |
| `LS-3` false terminal reconciliation | **Introduced, LC-1a.** `test_ls_3_terminal_reconciliation_matches_dispatcher_truth` compares delivered Terminal/record with dispatcher truth before settlement; injected disagreement prevents close and success replay. An injected internal disagreement alone is not a baseline defect; an actual supported baseline disagreement is. |
| `LS-4a` missing/duplicate admission rollback | **Baseline, LC-0.** `test_ls_4a_submit_session_rollback_converges` closes over the finite F1-F5/R1-R4 application-admission table and D1-D4 dispatcher cleanup table below. It records exact attempts and successful state transitions: each physical transition succeeds once, while the baseline may make an idempotent follow-up call. |
| `LS-4b` missing/duplicate application settlement | **Introduced, LC-1a.** `test_ls_4b_application_settlement_retries_only_unfinished_step` faults observer release, dispatcher close, exact detail retirement, and plan retirement once under one two-caller race; only the unfinished step retries. Delivery-factory failure is a separate zero-application-compensation row. |
| `LS-5` retained stream/callback | **Baseline, LC-0.** `test_ls_5_release_retires_stream_and_callback` proves observer lookup and subscriber custody disappear, callback count cannot advance, and a weak sink owner is collectible. |

LS-4a is a pre-migration characterization of the machinery LC-1a removes. It
is dispositioned and removed only after LS-4b passes at the new owner. The
enduring stop-detector set after LC-1a is LS-1, LS-2, LS-3, LS-4b, and LS-5.

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
| `LC-0a` | Freeze generated-ID equality/distinctness, corpus-version governance, exact LC-6 department retirement, and the retained-guard cost before production work. | `LC-0` | Focused oracle tests; unchanged frozen hash; documentation inspection; no production diff. | Complete |
| `LC-0b` | Settle the LS-1 normative contract, replace its timing-sensitive raw-order assertion with deterministic loss/duplication accounting, and withdraw the unsupported defect classification. | `LC-0a` | Finite normative audit; duplicate/loss self-tests; 30 fresh deterministic runs; T1 and production unchanged; ordinary/import gate. | Complete |
| `LC-1a` | Application becomes sole domain-effect owner; duplicate association/compensation/cleanup authority disappears; bounded adapter response replay and delivery shutdown remain. | `LC-0b` | T1 unchanged; disappearance/test symmetry; structural no-drain-cleanup proof; introduced LS-3 and LS-4b plus enduring T2; affected neighborhood. | Pending rebuild |
| `LC-2` | Observer/`SessionSubscription` solely owns physical observation lifetime without CLI/web timing change. | `LC-1a` | Barrier timing, observer fault matrix, T1/T2, interfaces. | Pending |
| `LC-3` | Compose live/stored session records without lock, concurrency, persistence, or public behavior change. | `LC-0b` only; independent of `LC-2` | Core/dispatcher, exact stored projection, T1 persisted bytes. | Pending |
| `LC-4` | Retain parallel maps and close disposable entry feasibility probe with truthful lock-ownership result. | `LC-3` | Scratch entry, finite mutators, AST plus instrumented condition, concurrency, full reversal. | Pending |
| `LC-5` | Run/reverse terminal-field probe inside exact derived twelve-file domain. | `LC-1a`, `LC-2`, `LC-3` | Exact diff, field-flow tests, no residual. | Pending |
| `LC-6` | Integrate/adversarially close and retire only temporary T1. | `LC-1a`-`LC-5` | Final T1 match; enduring tests; ordinary/headed/import/docs/cleanliness. | Pending |

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

### LC-1a recovery protocol

Recovery commit `dc94aef` is input, not a review unit. Create a fresh LC-1a
branch from the corrected guard baseline and inspect only
`git diff 197a2fc dc94aef -- <path>`. Reintroduce accepted content path by path;
never merge or cherry-pick the recovery commit. Retain the WIP branch until the
rebuilt atomic LC-1a commit passes its full gate. The port and strong indirect
import contract remain inside LC-1a. Command stripes remain only with explicit
single-flight and disjoint-command concurrency proof.

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

### LC-6 exact retirement and retained cost

LC-6 removes only the three temporary T1 artifacts and the single matching
`tools` department entry named in LC-0a. The enduring stop detectors,
observation barriers, positive-owner tests, `tests/test_task_lifecycle.py`, and
its `interfaces` department entry remain. The exact retiring and retained line
cost is recorded when LC-0a closes. The pre-amendment measurements were 1,653
temporary lines (905 runner + 601 baseline + 147 self-test) and 1,290 retained
guard lines. LC-0a measures 1,667 temporary lines (905 + 601 + 161) and the
same 1,290 retained lines. LC-0b makes the deterministic detector and its
fault self-test 1,389 retained lines. Remeasure again at LC-6: ordinary
`mechanism-removed`/`reanchored-owner` dispositions may shrink the retained
module, but wholesale teardown belongs to a separately reviewed post-register
test-consolidation checkpoint and is not authorized here.

## 6. Evidence and resumption

| Evidence | Result |
| --- | --- |
| Base | Clean `milestone1-anthony` at `5631066`; prior recovery commit `59affc4` remains isolated and is not a review unit. |
| Register refinement | User-adjudicated refinements incorporated 2026-09-02. LC-0a closes four nonblocking guard findings; LC-0b corrects LS-1. This repository document is now the sole maintained plan, and the `.codex` snapshot is intentionally left unchanged. |
| T1 stability | Three fresh processes and the frozen baseline are byte-identical: SHA-256 `AC08426E682BC362CC9E0CAB9A7ABE4FA998518DC5E9CCFD3FB0DF86F68CB53B`. The oracle rejects bridge, CLI, event-sequence, fixed drain-identity, persistence, and filesystem corruptions. |
| `DISC-B1` | With the CLI push callback blocked after `PhaseChanged`, cancellation is accepted and dispatcher truth reaches canceled before callback release; release then yields one Terminal, one terminal record, canceled exit mapping, exact stdout, and exact stderr. |
| `DISC-B2` | `begin_close` marks delivery closing, increments its generation, and wakes the blocked bounded offer before current `unsubscribe_all`; the baseline then releases the observer once and orders offer withdrawal, adapter unsubscribe, session close, and service close. This records current behavior, not target ownership. |
| T2 baseline | LS-1, LS-2, LS-4a, and LS-5 pass untouched production. The old LS-1 assertion intermittently rejected `[1, 2, 3, Gap@68(first_missed=4), Gap@4(first_missed=4), 141, ...]`; the finite normative audit established that this is permitted recovery rewind, not evidence of LS-1 loss or duplication. The corrected module is `19 passed`; its final barrier-forced LS-1 path is 30/30 across fresh processes, and deliberate duplicate/unannounced-loss corruptions fail. LS-3/LS-4b remain introduced LC-1a guarantees. |
| Test census | `docs/TASK_LIFECYCLE_TEST_LEDGER.md` contains 129 unique behavioral rows and eight unique helper rows over the exact seven-file corpus; all dispositions remain pending. |
| Broad baseline | LC-0b ordinary suite with required bundled Node: `4909 passed, 4 skipped, 28 deselected`; import law: 11 kept, 0 broken. An initial run without required Node had only the five expected runtime-availability failures and was rerun with the bundled executable. |
| Adversarial review | A separate read-only review found five guard defects; all were corrected and independently re-reviewed closed. No production file or lifecycle behavior changed. |
| LC-0a amendment | Ordered `[A, B, A, B]` normalization and fixed-ID preservation are explicit; runner/baseline format remain literal 1; frozen SHA-256 remains `AC08426E682BC362CC9E0CAB9A7ABE4FA998518DC5E9CCFD3FB0DF86F68CB53B`; oracle plus department checks are `27 passed`; the diff contains only this register and the oracle self-test. |
| LC-0b amendment | No normative global raw-Gap monotonicity clause exists; existing required browser witnesses intentionally repeat a synthetic Gap sequence. The corrected LS-1 detector uses explicit ejection/recovery/terminal barriers and finite missing-reliable intervals. T1 still matches, production and `event_bus.py` are unchanged, and the unsupported `BUGS.md` entry is removed rather than marked fixed. |

- **Current checkpoint:** LC-0b complete; LC-1a is pending a fresh rebuild from
  this corrected guard baseline.
- **Next action:** create the fresh LC-1a branch, use only path-scoped
  `git diff 197a2fc dc94aef -- <path>` recovery input, and reintroduce reviewed
  content according to the matrix above.
- **Recovery rule:** do not merge or cherry-pick `59affc4` or `dc94aef`; both
  recovery snapshots remain isolated and are not review units.
- **Stop:** any supported baseline defect, real-boundary drift, baseline LS
  consequence, nondeterministic T1, repeated-defect threshold, inability to
  preserve work, or required event/capacity change.
- **Resolved guard stop (2026-09-02):** the observed recovery rewind violated
  only an unsupported detector assertion. It did not establish the stated
  LS-1 consequence, so no product defect or production fix is authorized. The
  deterministic replacement closes the guard issue and permits LC-1a recovery.
