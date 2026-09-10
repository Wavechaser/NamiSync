# Bridge contract

This document owns the external, local desktop bridge: ingress and response encoding, command identity, event delivery, transport recovery, and focused bridge evidence. `INTERFACES.md` owns host/package and implemented task lifecycle; `PRESENTATION.md` owns trees and views. Core source owns exact Python event and result types. This document deliberately does not prescribe a future task representation, reservation scheme, DTO family, or command count.

## Scope and authority

The bridge adapts workflow facts for a local headed client. It does not decide sync policy, accept filesystem paths as authority, write the ledger, or own a second session lifecycle. Every request is bounded before construction of an interface or presentation value. The current desktop bridge accepts a complete serialized command envelope of at most 65,536 UTF-8 bytes; another external adapter must enforce an equal or stricter complete-request limit at its own ingress.

The source under `namisync/core/` is canonical for implemented Python fields, enums, and event-body pairs. External spelling remains a bridge obligation: absent is not `null`, JSON numbers are used only where JavaScript-safe, and byte quantities and filesystem times use canonical decimal strings where required; bounded counts remain safe integers. Reject unknown members, duplicate keys, invalid Unicode, nonfinite values, unsafe integers, noncanonical decimal strings, and invalid identifiers before dispatch. Failures are typed, bounded, and inert; raw paths, payloads, tracebacks, and exception text do not cross the boundary.

Identifiers are opaque. `HexId` is 32 lowercase hexadecimal characters; current task and slot identifiers have their declared prefix plus that suffix; other grammars belong to their subject contracts. A `SafeInt` is a non-Boolean JSON integer in `0..9_007_199_254_740_991`; `Scalar64` is a canonical unsigned decimal string within signed 64-bit range. `FileIndex128` stays canonical decimal text and is opaque identity, never JSON arithmetic. The complete current grammar is tested with the source-owned validators and browser policy mirror.

## Current event and drain protocol

Production core events are v5. There is no positive v3/v4 compatibility path. The bridge response envelope is independently v1; each live event carries the nested `schema_version: 5` and the exact `body_type`/`body` pair from `CORE.md`. A `SessionEventView` carries session id, positive sequence, strict UTC timestamp, schema version, body type, and body. A terminal `SessionRecordView` carries a non-null result consistent with its terminal state. A drain update is exactly `{update_type:"event",event:SessionEventView}` or `{update_type:"record",record:SessionRecordView}`. The response has no cursor, acknowledgement, receipt, has_more, or echoed replay value. A result-free snapshot is not a terminal update and cannot release a session.

`next_events` is the current observation operation. It identifies the task, exact session, fresh drain id, and optional positive replay sequence, returns the longest response-byte-admitted ordered prefix of zero to 64 updates and consumes only that prefix. The 8 MiB response wall may admit fewer than 64. The server wait is at most 25 seconds and the browser deadline is 30 seconds. A valid reliable envelope is at most 1,048,576 canonical UTF-8 bytes before sequence, queue, replay, subscriber, or audit mutation, so one valid queue head fits the response wall.

Progress is lossy and may be coalesced; numeric sequence holes alone do not trigger recovery. An explicit `Gap` is visible, stops later batch application, and starts recovery from its first missing sequence. Transport uncertainty uses a new drain id and replay from the last accepted non-Gap sequence plus one. The browser validates a whole response and applies it atomically: an invalid wrapper, order, lifecycle relation, Gap cursor, or reducer relation changes no accepted cursor and runs no callback. A matching leading Gap on recovery proves the prefix is gone; preserve it, apply the available tail, and do not loop. A terminal record stops draining without erasing a visible loss.

The adapter queue is bounded to 64 updates. New Progress replaces queued Progress or is discarded when reliable entries fill the queue. Reliable events and terminal records may evict Progress, never reliable data; an all-reliable queue backpressures its observation sink until drain or shutdown. One drain at a time owns a task; a competing drain supersedes and wakes the incumbent, waits within its bound, then returns the typed busy result. A progress-only drain may linger once for 150 ms from first availability without extending that deadline; reliable, Gap, terminal, recovery, close, and supersession wake immediately.

Terminal release and explicit task close are distinct operations. Releasing an exact terminal session unsubscribes/closes that session after terminal delivery while retaining the reviewed task; closing explicitly retires the task. No uncertainty route disposes of a task implicitly. Implemented ownership and cleanup sequencing are in `INTERFACES.md`.

### Progress reduction

Validation also preflights the applicable batch through a pure, immutable
Progress reducer before moving the cursor or invoking a callback. Its derived
view is supplied as the optional second `acceptUpdate(update, progressState)`
argument, so existing one-argument consumers remain compatible. Retained state
and the exposed view own only `phase`, `phaseAuthority` (`phase_changed`,
`progress`, or `unknown`), the latest accepted Progress body, and the derived
active item. `PhaseChanged` starts a fresh temporal domain only when its phase
changes; repeating the same reliable phase promotes authority without
discarding aggregate, item, or attempt comparisons. Progress must agree with
reliable `phase_changed` authority. After `Gap`, progress-only authority remains
lossy: a later self-described snapshot with a different phase replaces it and
starts a fresh temporal domain because the intervening reliable phase change
may be outside the retained replay tail. Same-phase Progress still retains all
comparisons. Aggregate item/work counters cannot regress. Known selected-item
admission is fixed,
executor byte admission is fixed once known, and verifier byte admission may
grow; an unknown aggregate total may become known once. One attempt's
determinate counters cannot regress,
change total, or reappear after becoming indeterminate. Attempt comparison is
bounded to the current active item, and a reset token must differ from that
item's current attempt token. A newer lossy snapshot may repoint activity to a
different item without an observed inactive snapshot or reliable outcome: the
intermediate clear is itself replaceable and may have been coalesced away.
That handoff says nothing about settlement, which remains outcome-owned. The
reducer nevertheless rejects adjacent reuse of one non-null attempt token
under two different item identities, because an attempt belongs to exactly one
item.

Reliable matching outcomes clear derived activity even if the later inactive
Progress snapshot was coalesced away. In the compound verify phase, an
`IntegrityOutcome` with the matching plan-operation id clears the active
`operation` identity without reinterpreting the outcome's reliable namespace.
The just-settled identity cannot become active again without an intervening
inactive snapshot, different active identity, or temporal domain.
An authoritative inactive Progress may also clear activity at a reporter's
exception boundary. `Gap` clears phase-dependent Progress state and temporal
comparisons; a later self-described v5 Progress may restore displayable phase
authority without reconstructing missed outcomes. `Terminal` and the terminal
session record clear Progress and remain final truth. A pause state does not
clear activity, and `current_path` never creates or joins identity. Callback
views are frozen copies, so presentation code cannot mutate retained authority.

## Command, retry, and concurrency rules

Origin and readiness authorization occur before command dispatch. Navigation or bridge reinjection cannot roll back an admitted action. The allowlist, exact payload validation, native picker confinement, hostile-text sinks, and logging privacy are bridge security requirements; external text remains text, never markup, a URL, code, or path authority.

A mutating user gesture with a receipt mints one `command_id` and reuses the identical intent after uncertain delivery. Lookup precedes live revision checks and outside work. The same id with changed intent is `command_conflict`; a new id alone may reach mutable authority. Replay means no repeated effect, not necessarily identical response bytes: return the current allowed projection. Reads, native picker interaction, drain recovery, and exact terminal release have their own finite retry rules and do not borrow mutating receipt semantics.

A command against a revisioned selection, lifecycle, view, projection, or result carries only the applicable expected revision. For new work, the guard and scope freeze occur under their one owner so checked intent and admitted scope cannot diverge. A conflict is a typed no-effect response; the browser rehydrates rather than guessing stale intent. Do not repeat an accepted filesystem, recorder, or lifecycle effect because a response was lost.

## Native posture and readiness

Only the packaged local document is trusted. The host forces Edge Chromium,
refuses MSHTML fallback, disables debugging/external navigation, and checks an
exact committed-source snapshot independently for each dispatch. Canceled
navigation does not change that snapshot; committed off-origin navigation does.
Attachment failure is sticky and refuses dispatch. Only `dispatch(command_json)`
is exposed; NamiSync adds no evaluate-js, Window.state, static-server domain API,
or constructed-JavaScript data channel. Pywebview's return escaper remains
covered by installed hostile-text witnesses on dependency changes.

The shipped page has exactly one CSP meta element, first in `head`, whose raw
ASCII value is below. Shipped source and the static expected literal independently
witness it; no generated HTML or extra Python policy constant replaces them.

```text
default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'
```

Readiness has a fixed five-second deadline from native `loaded`. The page installs
its neutral receiver before appearance/shell construction, then calls `shell_ready`.
Once the native surface is confirmed safe, the host posts exactly
`{challenge:HexId,kind:"namisync.readiness.v1"}`. Only a completed current-generation
post plus matching `readiness_echo` admits OPEN commands. The nonce proves liveness,
never origin or filesystem authority. Reload closes the generation before queued
posts run; each post rechecks currency. Buffered challenge arrival is retained.
`shell_ready` is unavailable after OPEN; an exact echo replay can still acknowledge.
False/uncertain echo permits one identical-payload retry. Appearance enhancement
can degrade without revoking a confirmed safe base surface.

## Current envelopes and admission

A request is one JSON string with exactly
`{schema_version:1,request_id:HexId,command:string,payload:object}`. Version 1 is an
integer, not Boolean; duplicate/unknown keys, invalid Unicode and nonfinite values
refuse. Input order/whitespace need not be canonical. A fresh request id identifies
each transport attempt independently of gesture identity. Success is exactly
`{schema_version:1,request_id:HexId,ok:true,result:...}`; failure is
`{schema_version:1,request_id:HexId|null,ok:false,error:{code,message}}`. Echo the id
only after its own grammar passes, otherwise null. HexId is 32 lowercase hex
characters; SlotId and TaskId prefix it with `slot-` and `task-` respectively.

The complete request is bounded to 65,536 UTF-8 bytes before decoding. The complete
response is bounded to 8,388,608 canonical UTF-8 JSON bytes (sorted keys, compact
separators, valid Unicode, no nonfinite values) before native construction.
An excess returns `response_too_large` without undoing an admitted action. At most
64 handlers are admitted; saturation is `bridge_busy`. Close waits at most 35
seconds for quiescence. These active bounds are independent of retired BR-G-45.

After handler reservation, trust recheck, envelope decode and allowlist lookup,
composition's `admit(name)` checks BOOTSTRAP/OPEN context before payload validation.
Refusal, failure or malformed admission is `bridge_unavailable`. The bridge forwards
opaque context; the command checks it before its validator. Native return custody
stays charged through exact worker exit and matching browser receipt, including
after origin loss; acknowledgement is cleanup-only and admits no command. DEFENSE
owns the trusted-base and acknowledgement policy.

The host contains obsolete pywebview return callbacks using that same document
generation. An existing native worker arms one thread-local return marker only
after dispatch finishes; the window evaluator consumes it once. Already retired
returns are skipped. A `JavascriptException` during return evaluation is contained
only if that captured generation retired; stable-generation JS errors, non-JS
errors and unrelated evaluations still propagate. No lock spans native evaluation.
This addresses callback destruction on reload, not an atomic JavaScript delivery
fence: a JS error racing retirement is treated as obsolete delivery. Command
effects, replay, response custody and actual worker-exit accounting are unchanged.
The adapter is pinned to pywebview's fresh-worker, single-return evaluation shape;
compatibility tests exercise that installed return path. The separately proposed
asynchronous command boundary in M1_PLAN remains unimplemented.

### Fixed errors

| Code | Message |
| --- | --- |
| `invalid_request` | The desktop request is invalid. |
| `unsupported_version` | Restart NamiSync to load a compatible desktop page. |
| `unknown_command` | This desktop action is not available. |
| `invalid_payload` | The desktop action contains invalid data. |
| `request_too_large` | The desktop request is too large. |
| `response_too_large` | The desktop response is too large. |
| `slot_unavailable` | That folder selection is no longer available. Choose both folders again. |
| `picker_unavailable` | The folder picker could not open. Try again. |
| `command_conflict` | This action no longer matches its first attempt. Start the action again. |
| `planning_refused` | NamiSync could not start a plan for those folders. Review both folders and try again. |
| `task_unavailable` | That desktop task is no longer available. |
| `drain_busy` | That desktop task already has an event request in progress. |
| `observation_conflict` | That desktop task is already observing different work. |
| `bridge_busy` | NamiSync is busy. Try this action again. |
| `bridge_unavailable` | NamiSync is closing or this desktop page is no longer trusted. |
| `internal_error` | NamiSync could not complete the desktop action. |

Structured refusals are definitive. Retry policy belongs to immutable command
rows and the wrapper, never handler data. No private detail is appended to errors.

## Implemented command map

These eleven rows are active in `namisync/interfaces/web/commands.py` and mirrored by
the packaged wrapper. Payload/result key sets are exact. SafeInt is a non-Boolean
integer in `0..9_007_199_254_740_991`; Theme is `system|light|dark`. Except the two
BOOTSTRAP rows, commands require OPEN.

| Command | Payload | Result | Deadline / retry |
| --- | --- | --- | --- |
| `shell_ready` | `{}` | `{acknowledged:true}` | BOOTSTRAP; 5 s; none |
| `readiness_echo` | `{challenge:HexId}` | `{acknowledged:boolean}` | BOOTSTRAP with exact post-open replay; 5 s; one identical-payload retry after false/uncertainty |
| `pick_folder` | `{purpose:"source"\|"target"}` | `null` or `{id:SlotId,display:string}` | interactive; no deadline or automatic retry |
| `create_task` | `{command_id:HexId}` | `{task_id:TaskId}` | 30 s; one same-command replay after uncertainty/reinjection/internal_error |
| `list_tasks` | `{}` | `{tasks:[{task_id:TaskId,session_id:null\|HexId,session_state:null\|"active"\|"completed"\|"failed"\|"canceled"\|"refused",session_released:boolean}]}` | 5 s; one identical-payload retry |
| `start_plan` | `{command_id:HexId,source_id:SlotId,target_id:SlotId,deletion_policy:null\|"trash"\|"additive"}` | `{task_id:TaskId,request_id:HexId,session_id:HexId}` | 30 s; one same-command replay after uncertainty/reinjection/internal_error; manual Retry retains id |
| `next_events` | `{task_id:TaskId,session_id:HexId,drain_id:HexId,replay_from:null\|positive-integer}` | `{task_id:TaskId,session_id:HexId,drain_id:HexId,updates:array}` | 30 s client / 25 s server; recovery mints a new drain id |
| `release_terminal_session` | `{task_id:TaskId,session_id:HexId}` | `{task_id:TaskId,session_id:HexId}` | 30 s; identical-payload recovery at 100/250/500 ms, then visible manual retry |
| `close_task` | `{task_id:TaskId,session_id:null\|HexId}` | `{task_id:TaskId,session_id:null\|HexId,disposition:"pending"\|"closed"}` | 30 s; identical-payload recovery at 100/250/500 ms, then visible manual retry |
| `read_cosmetic_section` | `{section:"appearance",value_version:1,applied_presentation_revision:SafeInt\|null}` | `{section:"appearance",value_version:1,revision:SafeInt,dirty:boolean,value:{theme:Theme}}` | 5 s; one identical-payload retry |
| `replace_cosmetic_section` | `{section:"appearance",value_version:1,expected_revision:SafeInt,value:{theme:Theme}}` | same cosmetic snapshot plus `disposition:"applied"\|"noop"\|"conflict"` | 5 s; no mutation retry, read after uncertainty |

Non-null replay sequences crossing the browser remain JavaScript-safe. Command id
and revision fields are forbidden unless named. Null deletion policy consumes the
service setting; mirror is not admitted here. A client deadline does not cancel
an admitted Python handler. Start replay resolves retained wire intent before
volatile slots: equal id/intent survives expiry; changed wire/resolved intent
conflicts. Lifecycle release/close uses exact owner identity and idempotent
recovery, not invented command receipts.

`create_task` publishes a process-live shell with no session, request, plan, or
result. `list_tasks` reconstructs published blank and session-backed tasks after
document reinjection; an active session is reported as `active`, while a
delivered terminal record keeps its actual terminal state before and after
session release. Blank close uses the exact null-session owner path. A live
session close first requests task-bound cancellation and returns `pending`; the
card remains until terminal delivery permits a replayed `closed` disposition.
Terminal-session release and task close remain distinct operations. The browser
rejects stale document, navigation, and list generations before adopting task
state.

### Slot lifetime

Only the native picker currently creates slots. A slot holds the real path,
purpose, inert display, fixed monotonic expiry 30 minutes after insertion, and
LRU recency. Lookup is nonconsuming and refreshes recency without extending expiry.
Sweep expired slots before insert/lookup; at most 32 unexpired entries exist.
At capacity evict the least recent, breaking ties by slot id. Start resolves both
live purpose-matching slots under one lock before updating either recency.
Fabricated, expired, evicted and wrong-purpose ids share `slot_unavailable`.
The browser sees only id/display and cannot promote display to path authority.
Workflow admission reprobes resolved roots. Future typed/recent inputs preserve
that outcome without inheriting the old prospective slot recipe.

## Current cosmetic channel

Appearance is the sole current mutable cosmetic section. It is exact, bounded, and non-semantic: accepted appearance changes do not alter settings policy, service/registry/planner state, plan fingerprints, tasks, or sessions. The browser reconciles a conflict or uncertain replacement through the declared read command instead of retrying an unknown mutation. Native material, high-contrast precedence, accent, and reduced-motion behavior remain system-owned presentation rules in `DESKTOP_UI.md`; the bridge only carries the typed section snapshot. Reads/replacements reject another section, another value version, unknown members, a non-JavaScript-safe revision, or a theme outside the three declared values before persistence or UI mutation.
Concurrent handlers synchronize effect admission, drains and retirement without holding adapter locks across workflow I/O. INTERFACES owns implemented lifecycle. Prospective generation pins, replacement leases and publication seals are not prescribed here.

## Accepted future outcomes

The next task/review surface must give users idempotent actions, stale-intent refusal, explicit close, truthful terminal delivery, bounded ingress and populations, and a finite containment/refusal/evidence design. The mechanism is open: future work must record its own bounded delivery register and name its runtime enforcer and evidence. Do not revive complete-owner-graph charging, byte reservations, phase-ahead leases, precharged response capacity, or an exact command-map expansion by citing this document.

Location admission remains a workflow-owned safety outcome: raw candidate text is bounded and classified through the common no-follow admission path; slots are purpose-bound, short-lived opaque references and fresh admission remains required at start. A slot is never a durable authorization or path-policy authority. Exact future Setup and task DTOs belong to their delivery register, not this document.

## Evidence and ongoing checks

`BR-G-42` owns focused scale evidence for bridge behavior; `DEFENSE.md` §7 classifies claims and `TESTS.md` owns collection/routing. The frozen historical v1 event-and-transport-custody claim is closed only for the representation, corpus, runner, and authority artifacts below:

- calibration-a: 1,376,690 bytes / 4,890 objects ordinary and 1,534,946 bytes / 5,499 objects exact maximum without Gap;
- ceiling: 1,966,080 bytes (1.875 MiB), frozen separately;
- independent holdout-b: 1,351,794 ordinary and 1,513,014 exact-maximum bytes, with three fresh runs below the ceiling and no Gap, ordered delivery, 128/64/64 queue shape, cleanup, and terminal predicates.

The authoritative committed artifacts are `tests/interfaces/web/sh_g_8_transport_calibration.json`, `sh_g_8_transport_ceiling.json`, and `sh_g_8_transport_holdout.json`. Calibration was produced from tested commit `56c50b43dc19090ad33af031891503bfec80599b`. The ordinary current-source one-child guard authenticates the frozen contract and compares both live custody shapes with its ceiling; it is Tier-1 drift evidence, not a recalibration. Terminal result graphs, whole-Job deltas, and whole-runtime resource acceptance are outside this closed custody claim.

The v4 installed-wheel timing and custody runs are retained historical diagnostic evidence. They do not establish current-source Tier-2 timing acceptance or alter the frozen v1 calibration. In particular, `sh_g_8_acceptance=incomplete-without-custody` remains incomplete evidence, not a pass. The benchmark command remains diagnostic; reproduce frozen custody only with the committed calibration runner and its validated artifacts. Any changed bridge transport must run its affected ordinary checks; new acceptance requires predeclared profile, authority, artifact, and validator rather than a favorable observation.

Useful failure checks remain mandatory: a valid event must not be stranded by a singular response overflow; an explicit Gap must not be hidden by terminal truth; a malformed batch must not partially apply; an uncertain replay must not repeat an effect; origin refusal and hostile-name rendering must make no handler or DOM authority; and a bounded queue must preserve reliable tail/terminal reconciliation under overflow.

Historical decision, gate, and delivery narrative is retained in `obsolete/M1_BRIDGE.md`. It is provenance only and cannot reactivate retired mechanisms or prescribe unrealized shapes.

## Focused measurement profile

The retained BR-G-42 reference profile is Windows 11 Pro build 26200, i7-13700K
(16 cores/24 logical processors), 63.7 GiB RAM, WD_BLACK SN850X 4 TB NVMe for
repository/fixtures/SQLite, CPython 3.13.14 and SQLite 3.50.4, AC power and no
unrelated sustained workload. P95 criteria use at least 30 warm samples; cold
maxima use at least five fresh-process or cold-projection samples. Record raw
samples, source/runtime/profile, fixture seed, statistic, run count, p95 and
maximum. These are a reference acceptance profile, not exact-version launch
admission. DEFENSE section 7 governs changed-profile and evidence decisions.

The event fixture is four active tasks for 60 seconds at 100 aggregate Progress
and 10 aggregate reliable events per second. Reliable/terminal delivery retains
100 ms p95 / 250 ms maximum with no Gap; replaceable progress retains 1 s p95 /
2 s maximum with coalesced monotonicity. Current-source timing acceptance is open.
The current v5 custody fixture and frozen v1 acceptance are distinct: per task,
150 reliable outcomes own items_done, while byte coordinates 1..1,500 drive
cadence with valid item/attempt identities and matching outcomes. Ordinary final
results retain the 1,500-byte attempted-work high-water; maximum-no-Gap remains
outcome-only. The active-version field overlay cannot alter the frozen v1 corpus.
The installed event diagnostic's coordinated producer/page/parent v5 migration
remains unassigned; historical v4 runs do not close current timing acceptance.

A new or changed transport representation retains the protected contract,
artifact/validator identity, realistic corpus, source/runtime/dependency admission,
ordered 128/64/64 queues, no-Gap, cleanup and terminal witnesses. The committed
runners and artifact validators under tests remain unchanged by this migration.
PRESENTATION owns its projection/gesture budgets under this shared profile;
HISTORY owns its query budgets. None is aggregate task-graph certification.
