# Bridge contract

This document owns the external, local desktop bridge: ingress and response encoding, command identity, event delivery, transport recovery, and focused bridge evidence. `INTERFACES.md` owns host/package and implemented task lifecycle; `PRESENTATION.md` owns trees and views. Core source owns exact Python event and result types. This document deliberately does not prescribe a future task representation, reservation scheme, DTO family, or command count.

## Scope and authority

The bridge adapts workflow facts for a local headed client. It does not decide sync policy, accept filesystem paths as authority, write the ledger, or own a second session lifecycle. Every request is bounded before construction of an interface or presentation value. The current desktop bridge accepts a complete serialized command envelope of at most 65,536 UTF-8 bytes; another external adapter must enforce an equal or stricter complete-request limit at its own ingress.

The source under `namisync/core/` is canonical for implemented Python fields, enums, and event-body pairs. External spelling remains a bridge obligation: absent is not `null`, JSON numbers are used only where JavaScript-safe, and byte quantities and filesystem times use canonical decimal strings where required; bounded counts remain safe integers. Reject unknown members, duplicate keys, invalid Unicode, nonfinite values, unsafe integers, noncanonical decimal strings, and invalid identifiers before dispatch. Failures are typed, bounded, and inert; raw paths, payloads, tracebacks, and exception text do not cross the boundary.

Identifiers are opaque. `HexId` is 32 lowercase hexadecimal characters; current task and slot identifiers have their declared prefix plus that suffix; other grammars belong to their subject contracts. A `SafeInt` is a non-Boolean JSON integer in `0..9_007_199_254_740_991`; `Scalar64` is a canonical unsigned decimal string within signed 64-bit range. `FileIndex128` stays canonical decimal text and is opaque identity, never JSON arithmetic. The complete current grammar is tested with the source-owned validators and browser policy mirror.

## Current event and drain protocol

Production core events are v5. There is no positive v3/v4 compatibility path. The bridge response envelope is independently v1; each live event carries the nested `schema_version: 5` and the exact `body_type`/`body` pair from `CORE.md`. A `SessionEventView` carries session id, positive sequence, strict UTC timestamp, schema version, body type, and body. A terminal `SessionRecordView` carries a non-null result consistent with its terminal state. A drain update is exactly `{update_type:"event",event:SessionEventView}` or `{update_type:"record",record:SessionRecordView}`. The response has no cursor, acknowledgement, receipt, has_more, or echoed replay value. A result-free snapshot is not a terminal update and cannot release a session.

Task terminal records describe the underlying plan, inventory or execution
session, even when the retained task kind remains sync-plan. Native and browser
validators preserve that closed kind/capability mapping: plan and inventory do
not support pause; execution does. A fast terminal result must reach the task
queue and release path just as a later result does. Exact source-owned record
validation remains in `task_port.py` and its browser consumer.

`next_events` is the current observation operation. It identifies the task, exact session, fresh drain id, and optional positive replay sequence, returns the longest response-byte-admitted ordered prefix of zero to 64 updates and consumes only that prefix. The 8 MiB response wall may admit fewer than 64. The server wait is at most 25 seconds and the browser deadline is 30 seconds. A valid reliable envelope is at most 1,048,576 canonical UTF-8 bytes before sequence, queue, replay, subscriber, or audit mutation, so one valid queue head fits the response wall.

Progress is lossy and may be coalesced; numeric sequence holes alone do not trigger recovery. An explicit `Gap` is visible, stops later batch application, and starts recovery from its first missing sequence. Transport uncertainty uses a new drain id and replay from the last accepted non-Gap sequence plus one. The browser validates the whole response before adoption: an invalid wrapper, order, lifecycle relation, Gap cursor or snapshot changes no accepted cursor and runs no callback. A matching leading Gap on recovery proves the prefix is gone; preserve it, apply the available tail, and do not loop. A terminal record stops draining without erasing a visible loss.

The adapter queue is bounded to 64 updates. New Progress replaces queued Progress or is discarded when reliable entries fill the queue. Reliable events and terminal records may evict Progress, never reliable data; an all-reliable queue backpressures its observation sink until drain or shutdown. One drain at a time owns a task; a competing drain supersedes and wakes the incumbent, waits within its bound, then returns the typed busy result. A progress-only drain may linger once for 150 ms from first availability without extending that deadline; reliable, Gap, terminal, recovery, close, and supersession wake immediately.

Terminal release and explicit task close are distinct operations. Releasing an exact terminal session unsubscribes/closes that session after terminal delivery while retaining the reviewed task; closing explicitly retires the task. No uncertainty route disposes of a task implicitly. Implemented ownership and cleanup sequencing are in `INTERFACES.md`.

The Plan execution summary carries nullable `started_at` and `ended_at` in the
same strict UTC form as `SessionRecordView`. Both are null until a matching
execution terminal record and retained result have been captured. After capture,
`ended_at` is required. `started_at` remains null when the dispatcher worker
never started; an unrun filesystem result may still have a worker start time.
The browser validates this exact shape on Plan summary and window reads;
neither time is inferred from event receipt or a local clock.

### M1-8-R0 active-operation anchor contract

`get_plan_anchor` admits exactly one
of two request shapes: the unchanged `{task_id:TaskId,expected_revision:SafeInt,
node_id:NodeId}`, or `{task_id:TaskId,session_id:HexId,expected_revision:SafeInt,
operation_id:HexId}`. Mixed or additional members refuse before dispatch. Both
return the unchanged `{disposition:"current"|"conflict",view_revision:SafeInt,
node_id:null|NodeId,index:null|SafeInt}`. The operation variant uses the retained
Plan projection's operation-to-node index and the existing visible-ancestor
resolver. Under the task lock, a different current session or view revision
returns conflict with the current view revision and null target. Existing
unavailable/retired-task refusal remains active. An operation absent from the
retained Plan is invalid; an excluded operation with no visible ancestor returns
current with null target. The synthetic root is never a visible target. Existing
node-anchor callers and complete-request ingress bounds remain unchanged. No selection, filter,
sort or execution mutation is authorized by lookup. Execution and post-copy
verification share operation identity; standalone integrity lookup is excluded.
The client coalesces to the latest target with bounded outstanding work and
retires replies after manual navigation or identity/view change. This is the
only R0 command extension; the Plan execution-summary response also carries
the terminal record times described above. Progress timestamp retention uses
existing event fields. PRESENTATION and DESKTOP_UI own view/interaction semantics.

### Authoritative task snapshots

The Python desktop adapter owns task presentation reduction and progress
estimation. Each drain response carries one detached, bounded snapshot with
an independent internal wire version, exact task/session identity and a safe
revision. `task_port.py` owns the drain wrapper; `web/task_snapshot.py` owns the
snapshot fields and reduces captured observations under the drain's existing
task owner. Browser
admission checks version, identity, revision, canonical scalars and renderable
shape before one atomic adoption. It does not replay progress or attempt rules.
The current internal snapshot version is 2. It publishes derived display facts
and active item identity, not the reducer's raw Progress, phase-authority,
attempt/counter copies or duplicate aggregate percentage.

Snapshot bytes participate in the same complete response ceiling as the event
prefix. Reduction and byte admission are staged from captured values; failure
cannot advance retained presentation state, pop unadmitted queue entries or
earn a terminal receipt. A non-leading recovery Gap ends the applicable prefix;
a matching leading replay Gap permits the available tail. Lost delivery may
leave native presentation ahead of the page: re-observation preserves the
newer native facts instead of reducing old events again. An old replay Gap
records uncertainty and rebases estimates without discarding newer progress.
Snapshot revision is local to its session: replacing a Plan session with an
execution session retires the prior snapshot before adopting the new session's
independent revisions. Renderers use only a snapshot bound to the current session;
Plan Gap is not execution history loss. Revision is presentation identity, not
effect authority or a new recovery protocol.

The snapshot carries lifecycle facts, the bounded terminal result, display and
explicit incomplete facts; it never carries a complete per-item outcome map.
The terminal result retains its phase and recording-issue feedback as well as
headline axes; these are already bounded public values. A new Gap clears
temporal comparisons and estimates, but its observed loss remains visible.
Later progress can supply a displayable phase without reconstructing missing
outcomes. Terminal truth clears activity without proving item completeness.
Windows and exact details retain their separate existing bounds and owners.

Python retains only current phase/aggregate and active-item/attempt comparison
state. Reliable phase authority, fixed admitted work, attempt identity and
counter advancement remain enforced there. Lossy handoff may change the active
item without an observed inactive event; that does not settle the former item.
Matching reliable outcomes clear activity, including automatic verification
joined by operation identity. New phase, Gap and terminal reset temporal state.
Progress estimates use one monotonic sample history and exact byte subtraction.
The sink stamps the accepted queued Progress; coalescing replaces that sample
time without moving the independent first-availability linger deadline. Byte
admission/retry uses the stored sample, not drain or browser-delivery time.
DESKTOP_UI owns their visible presentation policy.

Progress-comparison conflicts are presentation faults, not terminal authority:
discard the conflicting progress/phase comparisons and estimates, retain a
sticky visible inconsistent-progress diagnostic, and continue reliable/terminal
delivery. Log a bounded internal diagnostic without event content. Only these
semantic comparison faults are contained; malformed values, identity/sequence,
response byte limits and terminal-record contradictions still fail strictly.

Transport cursor/replay, callback failure and terminal delivery remain browser
responsibilities. A terminal snapshot alone does not authorize session release:
the matching terminal record must be successfully presented through the existing
delivery path. Retry retains the exact terminal presentation and snapshot.
Local drafts, focus, scrolling, command recovery handles and pending feedback
remain page-owned. None of these views grant mutable execution authority.
For terminal presentation a matching snapshot is the sole source of session
state, result and timestamps, including a null result while active. Retained
window results are a fallback only without that snapshot. Window-only counts
and trash details remain independently owned and require the matching captured
execution session; they cannot override snapshot result axes. The page does
not duplicate bridge revision admission or cache another terminal result copy.
The drain callback receives the snapshot with the last applicable update, or
`(null, snapshot)` for an empty catch-up. Raw-event diagnostics ignore that
snapshot-only notification rather than counting it as an event sample.

## Command, retry, and concurrency rules

Origin and readiness authorization occur before command dispatch. Document replacement cannot roll back an admitted action. A genuine replacement permanently retires this window's command authority; canceled navigation and same-document history leave it intact. Initial readiness, effect receipts, worker custody and normal close retain their owners. [INTERFACES.md](INTERFACES.md#logging-and-host-startup) owns the unsupported-reload presentation and restart contract. The allowlist, exact payload validation, native picker confinement, hostile-text sinks, and logging privacy are bridge security requirements; external text remains text, never markup, a URL, code, or path authority.

A mutating user gesture with an effect receipt mints one `command_id`. Duplicate intent lookup precedes live revision checks and outside work. The same id with changed intent is `command_conflict`; a new id alone may reach mutable authority. Application receipt replay means no repeated effect, not necessarily identical response bytes: it can return the current allowed projection. Desktop communication recovery instead observes the original transport request and its captured response; it does not submit another mutation. Reads and drain recovery retain their own finite retry rules.

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
64 exchanges are admitted; saturation is `bridge_busy`. Close waits at most 35
seconds for quiescence. These active bounds are independent of retired BR-G-45.

`web/bridge.py` captures each hostile response occurrence and charges its exact
canonical bytes before using the detached value. Ordinary responses validate
owned views while projecting JSON primitives. Continuation storage keeps its
separately validated typed snapshot; task drains validate the complete admitted
typed prefix before queue consumption and project only after that handoff.
The browser detaches native data at its adoption boundary and validates identity
before acknowledging result custody. A matching final response that fails
validation is acknowledged as an unusable, fixed outcome; this cleanup does not
adopt its payload or establish whether the effect succeeded. Foreign identities
do not earn that acknowledgment.

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
compatibility tests exercise that installed return path. Small asynchronous
commands still use that native path for their admission return.

### Small asynchronous native commands

Only `create_task`, `start_plan`, `start_inventory`, `refresh_inventory`,
`acknowledge_inventory`, `restore_inventory`, `plan_again`, `start_execution`,
`release_terminal_session`, `close_task` and `probe_recent_pairs`
select the `CommandSpec` small asynchronous work class. Native dispatch
validates the request and admitted context before starting one command worker.
Ordinary `BridgeDispatcher.dispatch()` and `CommandSpec.invoke()` remain
synchronous. Custom rows default to direct delivery, as do bootstrap, picker,
list, drain and cosmetic commands. A picker display path is not subject to the
smaller completion-message wall. Mutation wrappers retain their original request
while observing delayed or unavailable results; read-only probe deadlines remain.

The direct native transport remains
`{transport_version:1,response_token:HexId|null,response:BridgeResponse}`.
An accepted asynchronous return is
`{transport_version:1,response_token:HexId,completion:{phase:"completion",generation:SafeInt,request_id:HexId,completion_token:HexId}}`.
Its current-document completion is
`{kind:"namisync.command-completion.v1",phase:"completion",generation:SafeInt,request_id:HexId,completion_token:HexId,response:BridgeResponse}`.
Both objects have exact keys. `BridgeResponse` is the unchanged version-1
success/error envelope above. After validation and capture, completion cleanup uses the exact canonical
`ack:completion:<generation>:<request_id>:<completion_token>` string. It bypasses
normal command admission, origin/readiness and saturation, but can only settle
matching existing completion/result custody, including a retained result whose
post failed. It invokes no command. Native-return receipt acknowledgment remains
a separate phase; an asynchronous admission ACK does not retire the later result.

Direct and asynchronous calls share the 64-exchange bound. An asynchronous
exchange adds at most one worker and one completion; it creates no pending work
queue. Worker-start refusal invokes no handler. Accepted work continues despite
reload or close. Slot reuse waits for actual native-worker and command-worker
exit, native-return acknowledgment/retirement, and completion acknowledgment/
retirement. Producing a result, timing out, or failing to post is not worker
death. These count bounds make no whole-runtime memory or thread claim.

The browser bounds retained original attempts to 64, with at most one early
completion per asynchronous entry. Validate exact transport and command identity
before capture or cleanup; payload validation gates successful result adoption.
Cleanup uses at most two attempts with
one-second observation deadlines; its failure cannot turn a captured valid
response into a failed operation, including ordinary asynchronous reads. Adoption
does not wait for admission or completion cleanup ACK success. The host generation learned from validated
admission or trusted observation remains completion identity. An unsolicited
completion cannot create an entry or retire another request's result. Late
responses remain adoptable while their original identity/ownership is retained.
Replacement retires browser delivery without canceling admitted work.

The asynchronous read-only recent-pairs probe keeps its five-second caller
deadline. A pre-dispatch timeout retires its entry and cannot submit later.
After dispatch, caller timeout leaves the same bounded async entry responsible
only for exact late native/completion cleanup. Early completion still waits in
its existing single-message slot for admission identity. Unknown completion
messages earn no ACK; a lost first admission or failed cleanup can retain that
bounded custody until genuine document retirement. No read resubmission or
second cleanup registry is introduced.

### Original-result observation

The command registry and browser mirror call this classification `response_policy`
(`CommandResponsePolicy` in Python): it selects a caller deadline, observed
mutation recovery, interactive wait or feedback-only behavior. It is metadata,
not a new wire field or recovery protocol.

Original-result retention applies to `create_task`, `start_plan`,
`start_inventory`, `refresh_inventory`, `acknowledge_inventory`, `restore_inventory`,
`plan_again`, `start_execution`, `mutate_plan_selection`,
`mutate_plan_scope`, `mutate_plan_highlighted_selection`, `control_execution`,
`release_terminal_session` and `close_task`. Existing domain receipts do not
provide a complete replacement: they can expire with retirement, replay a current
projection or omit a no-effect disposition. No identical resend is introduced.

The same native dispatch entry point accepts the canonical control string
`observe:<original_request_id>:<original_command>` (at most 105 characters).
It requires the current trusted document, an allowlisted OPEN command and an
accepting host. It never invokes the original handler, grants another effect,
waits for a worker or allocates another effect exchange. It can read existing
custody even when all 64 exchanges are occupied. Malformed/untrusted/closed
requests return fixed false, treated as failed communication.

An authenticated observation has the exact keys
`{transport_version:1,state:"pending"|"ready"|"unavailable",generation:SafeInt,request_id:HexId,response_token:HexId|null,completion_token:HexId|null,response:BridgeResponse|null}`.
Ready carries the original response and native token; asynchronous results also
carry their original completion token. Pending carries no final response.
Unavailable carries null tokens/response and makes no effect claim: original
admission may still arrive, or ownership may have ended. A first admission loss
can leave the browser without a generation/token; current trusted observation
supplies them. Already known generation/token and original request id must match.

Original results use the existing custody registry and exchange capacity. Direct
results retain the 8 MiB response wall and asynchronous completions their 65,536
byte wall, with fixed bounded observation metadata outside that original response.
Bind original request identity before effect and refuse duplicate live identities.
Native post failure retires that delivery attempt, not the captured original.
Validated browser capture, or classification of a matching final response as
unusable, earns the existing direct native ACK or asynchronous completion ACK.
Until that acknowledgment, genuine document retirement, host close
or process loss, result custody stays charged; there is no timer eviction or
append-only history. Unacknowledged custody can refuse new work at capacity.
Retiring a response never substitutes for actual worker exit.

Observed commands have a bounded startup wait before dispatch;
startup failure cannot leave a continuation that submits the action later.
Once dispatched, a five-second
mutation delay triggers feedback and bounded observation, not
cancellation or resubmission. One automatic round makes at most three observations,
each with a one-second deadline and 100/250 ms inter-attempt waits. A valid pending
observation remains pending when the round ends; failed/unavailable communication
qualifies that feedback without asserting effect failure or success. If a direct
delivery has already failed, a pending observation offers **Check** rather than
claiming another response will arrive automatically. A live original delivery can
still complete automatically. Persistent unavailable communication also offers
normal application close/reopen and review of current state as a fallback; it
does not promise that Check can always recover the result. The original promise
stays pending while communication is unresolved and is the sole result-adoption
path. Explicit
**Check** runs another bounded read-only
observation round; it creates neither a new mutation nor a second adoption owner.
Interactive picker wait, startup, drain, shutdown and resource deadlines
retain their separate contracts. Successful pending Close is a real lifecycle
receipt; later settlement actions remain distinct from retrying its observation.
Automatic Close continuation requires both that exact pending receipt and terminal
observation, regardless of arrival order. Consume the terminal transition once;
an unresolved first response or another pending receipt cannot create a Close
submission loop. Further known-pending settlement remains an explicit action.

A captured final `internal_error`, `response_too_large`, or matching response
that fails validation can follow an effect, but the retained response cannot
improve through observation: native custody does not rewrite its final bytes.
Classify these as noncheckable `fixed-unknown`; retain a bounded `invalid_result`
diagnostic for validation failure. Acknowledge and retire
that completed transport entry while retaining the affected UI intent fence.
Show that the outcome cannot be confirmed and direct the user to close/reopen
NamiSync and review current state; do not offer a nonworking observation Retry.
The availability of a Check closure is not itself the ownership fence.
After such a captured noncheckable review/control response, a separate explicit
Cancel may target the same active execution unless the unknown action was itself
Cancel. The existing control attempt owns that Cancel and any original-result
observation; it cannot erase the review's retained warning or permit a second
unknown Cancel. In-flight protected review commands remain fenced.
Explicit Close may clean up after a fixed review/control error when the retained
review still identifies the exact native task/session pair. That cleanup uses
the existing native cancellation and settlement owner; it does not establish
the earlier action's outcome. Unknown starts, execution admission, release and
Close keep their own fences. Task Close exposes the same blocking reason used
by its handler.

The browser uses one attempt/completion path for direct and asynchronous
commands. Original-result observation is optional state on that attempt, not a
second delivery registry or result adopter. Ordinary read deadlines retain only
bounded late-completion cleanup; they do not adopt a result after caller timeout.
Each observed attempt exposes one stable recovery handle through its existing
callback, initially before dispatch and subsequently on state changes. Page
owners retain that reference and read its status, Check availability, checking
state and message; Check joins the existing bounded observation round. This
handle owns no second result promise. Page workflow stages, task/session/revision
guards and lifecycle settlement remain with their existing owners.

### Current-state command recovery

`update_plan_view`, `mutate_plan_highlight`, `replace_cosmetic_section`,
`admit_location` and `pick_folder` do not retain or observe original responses.
Their submitted promises have no elapsed-time effect deadline. The first four
have bounded startup waiting and delayed feedback; the picker retains its
interactive wait and one live picker owner. Worker/exchange/ACK custody stays
bounded independently of original-result retention. Valid direct response capture
survives cleanup failure; ACK remains best effort after validated capture.

View, highlight and theme recover through an authoritative current-state read
after failure or explicit Refresh. That read does not prove the earlier command
settled. A fresh action uses the displayed revision and new user intent; request
generations and revisions reject stale UI adoption. Folder editing or rechoice
can supersede an admission, with row/admission revisions suppressing late replies;
only the latest resolved choice may feed Start or batch capture. Neither kind of
uncertainty alone fences unrelated task Close or controls. Selection→Execute,
start/Close and receipt-retirement guards remain. No mutation is automatically
replayed and no new outcome store or protocol is introduced.

DocumentChannel owns a separate command FIFO under the same exchange bound and
one native post owner. Required readiness is selected first; an in-flight native
send is never preempted. Sent command receipts remain independently bounded:
queued, sending and awaiting-acknowledgement commands together cannot exceed
64. Waiting for one receipt cannot block another command's delivery or replay.
A pending appearance update gets a turn between command posts when its prior
appearance receipt has retired; one unacknowledged cosmetic message cannot
block command delivery. Replacement and close retire old queued, sending and
awaiting-acknowledgement completion delivery;
callbacks run outside bridge/channel locks. The existing atomic final epoch
check plus `PostWebMessageAsJson` gate remains under DEFENSE's pinned native
non-reentrancy premise.

Each complete command message is snapshotted to bridge-safe primitives and
bounded to 65,536 canonical UTF-8 bytes. Post-effect encoding or size failure
uses a fixed bounded uncertainty completion, never a pre-effect refusal or a
repeated handler. Actual post failure retires completion-delivery custody only;
the browser reaches its existing deadline/recovery path. Shutdown retires and
wakes delivery before its bounded worker wait, and an unfinished worker keeps
service shutdown retryable.

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

Explicit admission and payload refusals are definitive. `internal_error` after
admitted work may instead mean uncertain result delivery; the task-command
wrappers retain their existing uncertainty recovery. Retry policy belongs to
immutable command rows and the wrapper, never handler data. No private detail
is appended to errors.

## Implemented command map

These rows are active in `namisync/interfaces/web/commands.py` and mirrored by
the packaged wrapper. Payload/result key sets are exact. SafeInt is a non-Boolean
integer in `0..9_007_199_254_740_991`; Theme is `system|light|dark`. Except the two
BOOTSTRAP rows, commands require OPEN.

| Command | Payload | Result | Deadline / retry |
| --- | --- | --- | --- |
| `shell_ready` | `{}` | `{acknowledged:true}` | BOOTSTRAP; 5 s; none |
| `readiness_echo` | `{challenge:HexId}` | `{acknowledged:boolean}` | BOOTSTRAP with exact post-open replay; 5 s; one identical-payload retry after false/uncertainty |
| `pick_folder` | `{purpose:"source"\|"target"\|"inventory"}` | `null` or `LocationChoice` | interactive; no deadline or automatic retry |
| `read_setup` | `{task_id:null\|TaskId}` | `{task_id:null\|TaskId,snapshot:SetupSnapshot,recents:null\|RecentLocations}` | 5 s; one identical-payload retry |
| `probe_recent_pairs` | `{}` | `{pairs:[{mapping_id:LocationId,source_id:LocationId,target_id:LocationId,source_state:LocationState,target_state:LocationState}]}` | async-small; 5 s; no automatic retry |
| `prepare_setup` | `{options:SetupOptions}` | canonical `SetupOptions` | 5 s; one identical-payload retry |
| `admit_location` | `{purpose:"source"\|"target"\|"inventory",candidate:LocationCandidate}` or `{purpose:"source"\|"target"\|"inventory",continuation_id:SlotId,mount_index:SafeInt}` | `LocationChoice` | current-state recovery; 5 s feedback; no mutation replay |
| `create_task` | `{command_id:HexId}` | `{task_id:TaskId}` | observed original result; 5 s feedback; no mutation replay |
| `list_tasks` | `{}` | `{tasks:[{task_id:TaskId,task_kind:null\|"sync-plan"\|"inventory",request_id:null\|HexId,session_id:null\|HexId,session_state:null\|"active"\|"completed"\|"failed"\|"canceled"\|"refused",session_released:boolean}]}` | 5 s; one identical-payload retry |
| `start_plan` | `{task_id:TaskId,command_id:HexId,source_id:SlotId,target_id:SlotId,options:SetupOptions}` | `{task_id:TaskId,request_id:HexId,session_id:HexId}` | observed original result; 5 s feedback; no mutation replay |
| `start_inventory` | `{task_id:TaskId,command_id:HexId,root_id:SlotId}` | `{task_id:TaskId,request_id:HexId,session_id:HexId}` | observed original result; 5 s feedback; no mutation replay |
| `plan_again` | `{task_id:TaskId,command_id:HexId,source_mount:null\|string,target_mount:null\|string}` | `{task_id:TaskId,request_id:HexId,session_id:HexId}` | observed original result; 5 s feedback; no mutation replay |
| `open_plan_view` | `{task_id:TaskId}` | `PlanViewSummary` | 5 s; one identical-payload retry |
| `open_inventory_view` | `{task_id:TaskId}` | `InventoryViewSummary` | 5 s; one identical-payload retry |
| `refresh_inventory` | `{task_id:TaskId,request_id:HexId,command_id:HexId,expected_revision:SafeInt,node_id:null\|NodeId}` | `{task_id:TaskId,request_id:HexId,session_id:HexId}` | observed original result; 5 s feedback; no mutation replay |
| `acknowledge_inventory`, `restore_inventory` | `{task_id:TaskId,request_id:HexId,command_id:HexId,expected_revision:SafeInt,node_id:null\|NodeId}` | `InventoryVisibilityResult` | observed original result; 5 s feedback; no mutation replay |
| `update_inventory_view` | `{task_id:TaskId,expected_revision:SafeInt,search_query:string,filters:[InventoryFilter],sort_column:"path"\|"filename"\|"size"\|"mtime",sort_direction:"ascending"\|"descending",collapse_node_id:null\|NodeId,collapsed:null\|boolean}` | `InventoryViewSummary` | current-state recovery; 5 s feedback; no mutation replay |
| `get_inventory_window` | `{task_id:TaskId,expected_revision:SafeInt,offset:SafeInt,limit:1..256}` | `{disposition:"current"\|"conflict",view_revision:SafeInt,offset:SafeInt,total:SafeInt,rows:[InventoryWindowRow]}` | 5 s; one identical-payload retry |
| `get_inventory_detail` | `{task_id:TaskId,expected_revision:SafeInt,node_id:NodeId}` | `{disposition:"current"\|"conflict"\|"unavailable",view_revision:SafeInt,node_id:NodeId,detail:null\|InventoryCurrentDetail}` | 5 s; one identical-payload retry |
| `update_plan_view` | `{task_id:TaskId,expected_revision:SafeInt,search_query:string,filters:[PlanFilter],sort_column:"path"\|"filename"\|"size"\|"mtime",sort_direction:"ascending"\|"descending",collapse_node_id:null\|NodeId,collapsed:null\|boolean}` | `PlanViewSummary` | current-state recovery; 5 s feedback; no mutation replay |
| `get_plan_window` | `{task_id:TaskId,expected_revision:SafeInt,offset:SafeInt,limit:1..256}` | `{disposition:"current"\|"conflict",view_revision:SafeInt,offset:SafeInt,total:SafeInt,execution:ExecutionSummary,rows:[PlanWindowRow]}` | 5 s; one identical-payload retry |
| `get_plan_detail` | `{task_id:TaskId,expected_revision:SafeInt,node_id:NodeId}` | `{disposition:"current"\|"conflict",view_revision:SafeInt,node_id:NodeId,detail:null\|PlanNodeDetail}` | 5 s; one identical-payload retry |
| `get_execution_detail` | `{task_id:TaskId,operation_id:HexId,expected_execution_revision:SafeInt}` | `{disposition:"current"\|"conflict"\|"not-retained",execution_revision:SafeInt,operation_id:HexId,operation:null\|OperationItemView,automatic_verification:null\|IntegrityOutcomeView,evidence:null\|ExecutionEvidence}` | 5 s; one identical-payload retry |
| `get_plan_anchor` | `{task_id:TaskId,expected_revision:SafeInt,node_id:NodeId}` or `{task_id:TaskId,session_id:HexId,expected_revision:SafeInt,operation_id:HexId}` | `{disposition:"current"\|"conflict",view_revision:SafeInt,node_id:null\|NodeId,index:null\|SafeInt}` | 5 s; one identical-payload retry |
| `reveal_plan_move` | `{task_id:TaskId,expected_revision:SafeInt,node_id:NodeId}` | `{summary:PlanViewSummary,node_id:null\|NodeId,index:null\|SafeInt}` | current-state recovery; 5 s feedback; no mutation replay |
| `mutate_plan_selection` | `{task_id:TaskId,command_id:HexId,expected_view_revision:SafeInt,expected_selection_revision:SafeInt,node_id:NodeId,selected:boolean}` | `PlanViewSummary` | observed original result; 5 s feedback; no mutation replay |
| `mutate_plan_scope` | `{task_id:TaskId,command_id:HexId,expected_view_revision:SafeInt,expected_selection_revision:SafeInt,selected:boolean}` | `PlanViewSummary` | observed original result; 5 s feedback; no mutation replay |
| `mutate_plan_highlight` | `{task_id:TaskId,expected_view_revision:SafeInt,expected_highlight_revision:SafeInt,gesture:"clear"|"replace"|"toggle"|"extend"|"add-range"|"move_up"|"move_down"|"move_up_extend"|"move_down_extend",node_id:null\|NodeId}` | `PlanViewSummary` | current-state recovery; 5 s feedback; no mutation replay |
| `mutate_plan_highlighted_selection` | `{task_id:TaskId,command_id:HexId,expected_view_revision:SafeInt,expected_highlight_revision:SafeInt,expected_selection_revision:SafeInt,selected:boolean}` | `PlanViewSummary` | observed original result; 5 s feedback; no mutation replay |
| `start_execution` | `{task_id:TaskId,request_id:HexId,command_id:HexId,expected_revision:SafeInt,destructive_acknowledged:boolean}` | task/session start or `{disposition:"in-flight"\|"frozen"\|"conflict"\|"confirmation-required",revision:SafeInt,state:"reviewing"\|"committing"\|"committed",session:null\|{request_id:HexId,session_id:HexId}}` | observed original result; 5 s feedback; no mutation replay |
| `control_execution` | `{task_id:TaskId,session_id:HexId,action:"pause"\|"resume"\|"cancel"}` | `{code:string,session_id:HexId,before:null\|string,after:null\|string,detail:string,accepted:boolean}` | observed original result; 5 s feedback; no mutation replay |
| `next_events` | `{task_id:TaskId,session_id:HexId,drain_id:HexId,replay_from:null\|positive-integer}` | `{task_id:TaskId,session_id:HexId,drain_id:HexId,updates:array}` | 30 s client / 25 s server; recovery mints a new drain id |
| `release_terminal_session` | `{task_id:TaskId,session_id:HexId}` | `{task_id:TaskId,session_id:HexId}` | observed original result; 5 s feedback; no mutation replay |
| `close_task` | `{task_id:TaskId,session_id:null\|HexId}` | `{task_id:TaskId,session_id:null\|HexId,disposition:"pending"\|"closed"}` | observed original result; 5 s feedback; no mutation replay |
| `read_cosmetic_section` | `{section:"appearance",value_version:1,applied_presentation_revision:SafeInt\|null}` | `{section:"appearance",value_version:1,revision:SafeInt,dirty:boolean,value:{theme:Theme}}` | 5 s; one identical-payload retry |
| `replace_cosmetic_section` | `{section:"appearance",value_version:1,expected_revision:SafeInt,value:{theme:Theme}}` | same cosmetic snapshot plus `disposition:"applied"\|"noop"\|"conflict"` | current-state recovery; 5 s feedback; no mutation replay |

Non-null replay sequences crossing the browser remain JavaScript-safe. Command id
and revision fields are forbidden unless named. Starts submit complete canonical
options; mirror is not admitted here. A client deadline does not cancel
an admitted Python handler. Start replay resolves retained wire intent before
volatile slots: equal id/intent survives expiry; changed wire/resolved intent
conflicts. Lifecycle release/close uses exact owner identity and idempotent
recovery, not invented command receipts.

Initial inventory publication requires exact terminal delivery and successful
session release. A prior complete view remains readable during a new scan or a
failed replacement; its request identity continues to name that publication.
`InventoryViewSummary` carries task/request/location identity, view revision,
frozen scan metadata, complete-domain rollup and current search/filter/sort/collapse
state. Scan scope is a bounded descriptor naming the entire location, one exact
item, one recursive folder, or a multi-subject selection; it carries at most one
path, never the complete scope arrays. It belongs to the producing publication,
including while a newer scan is running or refused. `InventoryWindowRow` supplies server-derived frames and domain status,
raw size/mtime and rollup, or an informational warning. Its nullable
`recorded_checksum` is the stored attestation's 16-byte XXH3-128 digest as exactly
32 lowercase hex characters; it is null when there is no baseline, on synthetic
ancestors and on notices. It remains stored baseline evidence for modified,
missing and reappeared rows and never claims verification of current bytes.
The source-owned exact
shapes are serialized by `inventory_review.py` and validated by `bridge.js`.
`InventoryFilter` admits present, unverified, verified, modified, reappeared,
unsupported, missing, mismatched, acknowledged and notice. Path sort is ascending
only; reset is an explicit path/ascending gesture. Windows contain at most 256
rows and conflict replies contain no rows. Current detail returns a fresh
location-scoped ledger row, observed stat and optional attested subject/content
evidence. Signed-64 scalars and full native file indexes cross as decimal text;
digest and provenance remain raw. Removed/renamed rows return unavailable.
Task/session/request/generation and view revision fence adoption after the read;
warnings and synthetic ancestors cannot trigger ledger detail reads. These four
commands grant no visibility mutation or integrity authority themselves.

`refresh_inventory` requires the exact current released task request and retained
view revision. Its optional node is resolved server-side into full, exact-leaf or
recursive-folder scope; warning nodes refuse before scan work. No client path or
location enters this command. Each original success or failure is retained until
task Close under the existing shared 48 start-response bound, reserved before
effect. A fresh command can retry from a prior complete view after an unavailable
root returns. Capacity refusal uses the fixed `inventory_capacity` message and
directs the user to close a task before refreshing. Replacement publication
advances the view revision and preserves
search, facets, sort and surviving collapsed folders; failed construction leaves
the old publication intact. Scan completeness remains separate from projection
completeness.

Visibility requires the current released request, a matching complete publication
and its exact revision. Full/root, folder and leaf membership comes from the
server projection; only its missing rows participate, including acknowledged
rows and subjects outside the visible window or current search/facets/collapse.
Warnings refuse before ledger work. Each row uses the existing conditional write,
so a reappeared or removed subject is stale rather than changed.
`InventoryVisibilityResult` has task/request/action identity, `expected_revision`,
`total`, `applied`, `noop`, `stale`, `conflict`, `unresolved_count`, and
`disposition:"completed"|"partial"`. Counts describe confirmed outcomes and sum
to total; a failed row may have committed and joins the unresolved suffix.
Completed means all row dispositions are known, not that all rows were changed.
The server freezes the original UTC timestamp and retains this bounded aggregate
before rebuilding the view. Original-result delivery settles after the complete
replacement attempt; a failed build preserves prior reads but blocks another
visibility effect until open publishes a whole replacement. Refresh may recover.
Visibility and starts share the existing 48 retained entries, reserved before
effects and pruned at exact task Close. No full per-row tuple crosses the wire.
The desktop keeps each original Refresh or visibility recovery handle with its
task across navigation and offers Check original outcome when delivery is
uncertain, without resubmitting the mutation. A successful same-task Refresh
hands observation to the fresh session before terminal release and view reload.
The browser accepts result counts only from the observed original command,
guards new actions by current task/request/view identity, and leaves warnings
inert. A failed visibility rebuild blocks another visibility effect until whole
reload confirms the publication; Refresh remains eligible from the retained
prior revision. Capacity refusal gives the fixed Close-a-task guidance.

`PlanViewSummary` has exactly `disposition`, `task_id`, `request_id`,
`view_revision`, `selection_revision`, `selection_state`, `source_path`,
`target_path`, `selected_operation_count`, `selectable_operation_count`,
`scope_selected_operation_count`, `scope_selectable_operation_count`,
`operation_count`, `preflight_ready`, `preflight_refusal_count`, `warning_count`,
`requires_destructive_confirmation`, `irreversible_update_count`,
`destructive_operation_count`, `destructive_operation_counts`,
`irreversible_operation_count`, `required_bytes`,
`visible_row_count`, `search_query`, `filters`, `sort_column`, `sort_direction`,
`collapsed_count`, and `execution`. The view disposition is `opened|current|applied|noop|conflict|in-flight|frozen`;
selection state is `reviewing|committing|committed`. `PlanWindowRow` is the exact
source-owned projection row serialized by `commands.py`; all scalar counts and
revisions remain JavaScript-safe. `NodeId` is `node-` plus 32 lowercase hex
digits. `PlanFilter` is one of the exact plan operation/status filter values
validated by the command table. Path sort admits ascending only, and a collapse
node and Boolean state are either both null or both present.

`execution` is exactly `{execution_revision:SafeInt,session_id:null|HexId,
result:null|OperationResultView,failed_operation_count:null|SafeInt,
disk_capacity_failure_count:null|SafeInt,gap:null|{minimum_first_missed_seq:
PositiveSafeInt,maximum_first_missed_seq:PositiveSafeInt},trash_location:null|
string,refusal:null|{origin:"preflight"|"commitment"|"other",codes:[RefusalCode]}}`.
The summary also carries the nullable record timestamps described above.
Refusal codes are distinct closed values from `core/preflight.py`, bounded by
that finite vocabulary. Only an unrun refused execution has a non-null refusal;
preflight has at least one code, commitment and other have none. The existing
retained execution capture preserves this disclosure before session details
are retired. No private paths, diagnostic text or commitment error cross it.
Before execution every field except revision is null. A live execution
has a session and null terminal result/count/trash fields. Only captured retained
truth fills those terminal fields. Gap extrema describe all observed first-missed
sequences regardless of arrival order. Gap facts may coexist with terminal truth and
are never interpreted as a count or complete lost range.

Every `PlanWindowRow` adds `execution`, which is null for a structural row and
otherwise exactly `{operation:null|CompactOperationResult,
automatic_verification:null|CompactIntegrityResult,evidence:null|
ExecutionEvidence}`. Compact operation result is exactly `{result,reason,
recording,recording_reason,detail_omitted_count}`; compact integrity result is
exactly `{result,reason,recording,record_disposition,detail_omitted_count}`.
Their closed enum and cross-field rules are the corresponding event-v5 rules.
Evidence is null before retained review. Otherwise it is exactly `{state,
content}`, where state is `recorded-copy|already-verified|unrecorded|superseded|
not-applicable`; content is present only for the first two states and is exactly
`{algorithm:"xxh3_128",digest:32-lowercase-hex,size:Scalar64,
provenance:"copy"|"readback"|"verify",observed_at:UTC timestamp}`.

`get_execution_detail` admits one exact operation already present in the Plan's
immutable operation mapping. `not-retained` is the actionable live result: it
contains null item/evidence fields and means retry after terminal session release;
it does not invent terminal truth. `conflict` reports the current execution
revision with null item/evidence fields. `current` is available only from the
captured review and returns the exact full operation item, exact full automatic
verification item and current evidence independently; a missing item remains
null. All response variants remain inside the existing 8 MiB wall.
Plan window totals, offsets, visible/parent/first-child indexes and anchors
exclude the synthetic projection root. Its direct children have depth zero
and no public parent; an anchor resolving only to the root returns null.

`reveal_plan_move` admits one current informational prior-group node, whose
server-owned peer names the canonical destination. Under the task/view owner it
stages obstructing query removal and ancestor expansion before publishing one
revision. A stale request has no effect and returns a conflict summary with
null node/index. This changes presentation only; selection and effects retain
their ordinary authority. The browser refetches at most 256 rows at the returned
index, guarded by task, view and foreground generations.
Plan window rows carry `move_group:null|{count:positive-SafeInt,destination_display:string}`;
only prior groups carry it, and their `move_peer_id` is the canonical reveal
target. Destination display is a hint of at most 255 UTF-16 units, empty for root;
an omitted ancestor prefix is rendered as `…\\`. It is never path authority.
All row displays and nullable notices are bounded to 300 UTF-16 units without
splitting Unicode characters. Exact originals remain in the server projection.
Rows also carry nullable `presentation_kind` and `prior_name` alongside the
unchanged `operation_kind`. Projection supplies the display/filter kind:
`rename` combines RECASE and same-Windows-parent pure MOVE, `move` is
cross-parent MOVE, and `move_update` stays distinct. Other kinds retain their
operation spelling. Structural rows have no presentation kind; prior rows
retain their display kind but have no `prior_name`. Only canonical rename rows
carry the old filename, bounded to 255 UTF-16 units. The admitted kinds form a
closed set: identity pairs except `recase→rename` and `move→move|rename`;
operation and presentation kinds are null together. The Plan filter and count category `rename` replaces `recase`;
`recase` is no longer an admitted Plan filter. Selection and execution continue
using original operation identities and kinds.

`PlanNodeDetail` is exactly `{path,prior_path,move_destination_path,path_origin,notice}`.
The three path fields are nullable original-spelling root-relative paths, bounded
by the existing 32,767 UTF-16-unit path contract (empty denotes root).
`path_origin` is `source|target|null` and is null exactly when `path` is null.
Canonical operations and prior-location nodes use target paths; scan notices
retain the scanned side. Groups carry only their destination path and notices
without a location carry no path origin. `notice` is nullable complete inert
Unicode text. Scan-warning diagnostics retain their existing 1,024-byte source
bound plus the supported path and fixed label text; refusal diagnostics have no
separate source text ceiling. Exact detail uses the existing complete 8 MiB bridge
response admission and explicitly refuses an oversized response.
The read admits one opaque node id from the current immutable Plan projection,
refuses the synthetic root, and returns null detail on a view-revision conflict.
It performs no filesystem or ledger read and is available during planning.

`PlanViewSummary` also carries `highlight_revision`,
`highlight_anchor_node_id`, `highlight_focus_node_id`,
`highlight_focus_visible_index`, and `highlighted_count`. A window carries the
matching `highlight_revision`; each row carries a Boolean `highlighted` flag.
Highlight commands never carry operation-id arrays. The task owner resolves a
compact gesture or highlighted range under the expected revisions, and a stale
request has no effect. Highlight state is presentation-only until the explicit
highlighted-selection command applies the resulting operation set through the
ordinary dependency and safety rules.

Selection facts come from the workflow's effective selection. Required bytes use
canonical nonnegative signed-64-bit decimal text; operation counts are SafeInts.
Confirmation is required exactly when `destructive_operation_count` is positive.
The browser does not infer this requirement from visible rows or filters.
`destructive_operation_counts` is exactly `{update,move_update,trash,delete}`,
with a SafeInt for every kind including zero; their sum is the destructive total.
`irreversible_update_count` counts selected UPDATEs without trash backup, and
`irreversible_operation_count` adds selected DELETEs. These separate facts allow
accurate replacement, removal and recoverability wording without changing policy.
Scoped selection commands carry no operation-id array. The task owner checks
both revisions and resolves all selectable operations whose own rows match the
active search/filter query, regardless of window, collapse or sort. A node
gesture intersects that set with the node's subtree. No query change itself
mutates selection, and an empty scope is a no-effect response. Workflow
dependency closure and safety exclusions retain authority over the resulting
complete selection.
Plan view-open consumes the service's revision-bound internal projection and
aggregate summary; it does not transport a per-operation public preview.

The browser publishes local pending feedback before awaiting view, selection,
Execute, or control receipts. That feedback grants no authority. View and
selection responses are adopted only for their exact task and generation;
Execute custody survives navigation once admitted so the exact returned session
is attached without a duplicate start. Controls bind the exact current task and
session identity. A retired planning or prior execution session cannot control a
replacement. Negative review-preflight facts remain immutable review context;
post-admission preflight refusal leaves selection committed and execution unrun.
Execute against an already refused reviewed plan returns the named
`preflight-refused` admission with its bounded preflight disclosure, null
session and reviewing state. It neither commits selection nor starts a worker.
Other admission outcomes carry a null refusal. The browser preserves the
original-command receipt flow and renders fixed actionable text from the
codes. After terminal release the existing Plan reload reads the retained
execution disclosure, including for fast refusals and later navigation.

Execute freezes task id, request id and selection revision before opening the
destructive confirmation dialog. Cancel sends no command; Confirm submits that
same snapshot with acknowledgment. Non-destructive scope submits immediately.
The backend validates request/revision, commits selection and admits execution
within the same command; there is no separate validation/go response. Stale
snapshots receive a no-effect refusal, never refreshed consent. Receipt recovery
retains the exact command and snapshot, fencing selection and Close until the
admission result is known. DESKTOP_UI owns modality and focus behavior.

`probe_recent_pairs` reads at most five remembered pairs, deduplicates at most
ten endpoint resolutions, and returns only exact IDs and raw states. LocationId
is a canonical positive decimal string in the existing signed 64-bit identity
domain. LocationState uses the same closed state vocabulary as LocationChoice.
The result forbids additional fields and duplicate mapping IDs. No choice slot,
continuation, task, session or durable record is created. Its worker uses the
existing resolver directly, separately from the initial Setup read. The browser
coalesces refreshes, rejects replaced-page/list observations and matches all
three IDs before displaying a status. A five-second deadline marks the status
unknown; it does not cancel native work or authorize automatic retries. Online
does not replace fresh admission when selecting or starting.

`create_task` publishes a process-live shell with no session, request, plan, or
result. `list_tasks` observes published blank and session-backed tasks within
the current document; an active session is reported as `active`, while a
delivered terminal record keeps its actual terminal state before and after
session release. Blank close uses the exact null-session owner path. A live
session close first requests task-bound cancellation and returns `pending`; the
card remains until terminal delivery permits a later exact close to return `closed`.
Terminal-session release and task close remain distinct operations. The browser
rejects stale document, navigation, and list generations before adopting task
state.

After active update delivery exhausts its automatic recovery budget, the browser
retains the exact drain in a suspended state. The task's explicit Retry updates
action restarts observation with a fresh drain id and non-null replay sequence
after the last successfully presented event; it does not restart domain work.
Controls remain unavailable until current recovery delivery is validated. Close
can still request cancellation for that exact retained session, and a pending
Close permits observation recovery so terminal delivery can finish retirement.
Terminal presentation and session-release retries retain their own owners.

Once exact terminal Close begins, the browser fences that task/session pair from
new drains and replacement work until the close receipt is known. An uncertain
result retains the same fence and only observation of that original Close may recover it;
`task_unavailable` cannot be treated as proof of completion or used to mint a
new intent. A `pending` receipt clears the terminal-retirement fence and resumes
ordinary draining because cancellation has not yet retired the task. A `closed`
receipt removes the task. Backend retirement independently rejects Plan view,
selection, Execute and Plan-again admission after terminal retirement begins.

The browser retains the existing exact create/start request after uncertain
delivery. New task, Setup and its batch coordinator expose its observation-only
retry closure. Retry queries that original request without another submission;
it cannot substitute newly edited roots/options or silently create a
replacement batch task. Definitive refusals and uncertain outcomes remain
distinct. No effect queue or durable receipt is added.

### Slot lifetime

Resolved typed, picker and remembered candidates create startable slots. An
ambiguous picker may instead create a non-startable continuation. Both share
one slot table. A slot holds the candidate,
purpose, inert display, fixed monotonic expiry 30 minutes after insertion, and
LRU recency. Lookup is nonconsuming and refreshes recency without extending expiry.
Sweep expired slots before insert/lookup; at most 32 unexpired entries exist.
At capacity evict the least recent, breaking ties by slot id. Start resolves both
live purpose-matching slots under one lock before updating either recency.
Fabricated, expired, evicted and wrong-purpose ids share `slot_unavailable`.
The browser cannot promote display to path authority. Workflow admission
reprobes candidates at a real start; the slot does not preserve mount authority.

### Setup and location values

`SetupOptions` has exactly `filters`, `deletion_policy`, `trash_on_update`,
`preservation`, `propagate_source_casing`, and `verify_after_execute`.
Preservation has exactly `preserve_ads`, `preserve_created`, and `preserve_acl`.
All switches are booleans, ADS must be false, and deletion is trash or additive.
Filters contain at most 64 strings, each at most 1,024 UTF-8 bytes and together
at most 16,384 bytes before normalization. Existing backend `FilterSet` grammar
and canonicalization apply; the browser never normalizes or deduplicates them.
Defaults prepopulate the form, and `prepare_setup` freezes one complete value
per gesture without writing global settings.

`LocationCandidate` is exactly `{kind:"literal_path",path,selected_mount}` or
`{kind:"remembered_location",location_id,selected_mount}`. A mount is null or
an explicit current choice; location ids use Scalar64 encoding. `LocationChoice`
has exactly `purpose`, `state`, `choice_id`, `continuation_id`, `display`, `location_id`,
`candidates`, and `detail`. Only `resolved` supplies a slot id. Other states are
`invalid_path`, `missing`, `not_directory`, `reparse`, `placeholder`, `remote`,
`unsupported_volume`, `offline`, `ambiguous`, `unavailable`, and `changed`.
Displays and detail are nullable inert strings, candidates are inert mount
strings, and location id is nullable. Admission and reading recents create no
task, session, receipt, mapping, run or recent activity.

An ambiguous picker supplies only a nullable `continuation_id`, never a
startable `choice_id`. The continuation retains first-admission identity and
the ordered displayed mounts; the browser submits an index after an explicit
choice. Native code resolves that index, re-admits outside the slot lock, and
compares volume identity, relative root, location identity and the exact current
mount tuple before returning a resolved choice. A continuation cannot be used
for Start. Replacement identity or changed mounts require fresh resolution;
display text and the initial picker gesture cannot substitute for clone choice.
The immutable continuation projection and prospective response together must
fit the existing 8 MiB direct-response bound before insertion or eviction. The same
32-slot population and fixed expiry apply; long paths never need to return as
an oversized follow-up request.

`SetupSnapshot` has exactly `setup_state` (default or frozen), `task_kind`,
`source`, `target`, `root`, `options`, and `plan_again`. A root is null or
`{display,location_id}`; task kind is null, sync-plan or inventory, and options
are null or `SetupOptions`. Inventory has only a root and no sync options.
`plan_again` is null or fresh read-only source/target states and candidate
mounts (`source_state`, `source_candidates`, `target_state`,
`target_candidates`). It is separate from the frozen inputs and grants no
authority. States are resolved, offline, ambiguous, missing, unavailable, or
changed. Frozen inputs alone do not establish a plan artifact: desktop readback
returns nonnull `plan_again` only after retrieving that artifact, including when
its reviewed locations are currently unavailable. `read_setup` with null task
returns defaults and recent sources,
targets and pairs; a task id returns one exact snapshot and null recents.
`RecentLocations` has exactly `sources`, `targets`, and `pairs` arrays, each
with at most five entries. Each recent location has exactly `location_id`,
`display`, `last_used_at`; each pair has exactly
`mapping_id`, `source`, `target`, `last_used_at`. Timestamps use UTC encoding;
no persisted drive hint crosses the bridge as a current mount.

Plan/inventory start atomically attaches the first session to the exact blank
task. Refusal leaves that shell available; it does not create a replacement.
Equal replay precedes volatile choice or native access. Plan again requires the
old artifact's reviewed bindings and freshly resolves both identities. Optional
mounts must match their current candidates; they cannot replace roots, options,
selection or authorization. A changed mount choice uses a new command id.
Success creates a separate task with frozen options and default selection.
Async responses remain identity-only; task enumeration never embeds Setup.
Per-task direct readback keeps valid long inputs out of small completion and
aggregate task-list limits.

## Current cosmetic channel

Appearance is the sole current mutable cosmetic section. It is exact, bounded, and non-semantic: accepted appearance changes do not alter settings policy, service/registry/planner state, plan fingerprints, tasks, or sessions. The browser reconciles uncertain replacement, known result or conflict through canonical current-section reads; it does not retain or observe the original replacement result. A fresh explicit change uses the displayed revision and never automatically repeats an unknown mutation. Native material, high-contrast precedence, accent, and reduced-motion behavior remain system-owned presentation rules in `DESKTOP_UI.md`; the bridge only carries the typed section snapshot. Reads/replacements reject another section, another value version, unknown members, a non-JavaScript-safe revision, or a theme outside the three declared values before persistence or UI mutation.
Concurrent handlers synchronize effect admission, drains and retirement without holding adapter locks across workflow I/O. INTERFACES owns implemented lifecycle. Prospective generation pins, replacement leases and publication seals are not prescribed here.

## Remaining future outcomes

Future inventory, integrity, execution-detail and history surfaces must retain the implemented task/review guarantees: idempotent actions, stale-intent refusal, explicit close, truthful terminal delivery, bounded ingress and populations, and a finite containment/refusal/evidence design. Each future mechanism must record its own bounded delivery register and name its runtime enforcer and evidence. Do not revive complete-owner-graph charging, byte reservations, phase-ahead leases or precharged response capacity by citing this document.

Location admission and typed/picker/recent Setup are implemented through the
common workflow-owned no-follow path. A slot, candidate or remembered identity
is never durable authorization or path-policy authority. Future commands must
preserve these outcomes without inheriting retired representation recipes.

## Evidence and ongoing checks

`BR-G-42` owns focused scale acceptance for bridge behavior;
[PERFORMANCE](PERFORMANCE.md) owns measurement methods, profiles and recorded
observations. `DEFENSE.md` §7 classifies claims and `TESTS.md` owns test routing.
The frozen historical v1 event-and-transport-custody claim is closed only for
its named representation, corpus, runner and committed authority artifacts.
The [recorded calibration and holdout](PERFORMANCE.md#bridge-transport-custody)
remain below the separately frozen ceiling with no Gap, ordered delivery,
128/64/64 queue shape, cleanup and terminal predicates.

The authoritative committed artifacts are `tests/interfaces/web/sh_g_8_transport_calibration.json`, `sh_g_8_transport_ceiling.json`, and `sh_g_8_transport_holdout.json`. Calibration was produced from tested commit `56c50b43dc19090ad33af031891503bfec80599b`. The ordinary current-source one-child guard authenticates the frozen contract and compares both live custody shapes with its ceiling; it is Tier-1 drift evidence, not a recalibration. Terminal result graphs, whole-Job deltas, and whole-runtime resource acceptance are outside this closed custody claim.

The v4 installed-wheel timing and custody runs are retained historical diagnostic evidence. They do not establish current-source Tier-2 timing acceptance or alter the frozen v1 calibration. In particular, `sh_g_8_acceptance=incomplete-without-custody` remains incomplete evidence, not a pass. The selected `python -m tools performance bridge-event installed --json build/bridge-event.json` case remains diagnostic: it measures archived-HEAD product bytes with a labeled working-tree driver and reports incomplete native attempts with raw child context. Its v5 page decodes fixture byte strings to bounded numeric samples, checks item-free terminal facts, and uses the ordered ItemOutcome stream as the independent item witness. A rejected report stops sample admission and publishes the first browser failure before Close; synthetic workers honor cancellation so host cleanup can settle. A timed-out historical launch alone does not establish its cause. Reproduce frozen custody only with the committed calibration runner and its validated artifacts. Any changed bridge transport must run its affected ordinary checks; new acceptance requires predeclared profile, authority, artifact, and validator rather than a favorable observation.

Useful failure checks remain mandatory: a valid event must not be stranded by a singular response overflow; an explicit Gap must not be hidden by terminal truth; a malformed batch must not partially apply; an uncertain replay must not repeat an effect; origin refusal and hostile-name rendering must make no handler or DOM authority; and a bounded queue must preserve reliable tail/terminal reconciliation under overflow.

Historical decision, gate, and delivery narrative is retained in `obsolete/M1_BRIDGE.md`. It is provenance only and cannot reactivate retired mechanisms or prescribe unrealized shapes.

## Focused measurement profile

[PERFORMANCE](PERFORMANCE.md#reference-profile-and-collection) owns the retained
reference profile, sample aggregation and event fixture. Reliable/terminal
delivery retains 100 ms p95 / 250 ms maximum with no Gap; replaceable progress
retains 1 s p95 / 2 s maximum with coalesced monotonicity. Current-source timing
acceptance is open.
The current v5 custody fixture and frozen v1 acceptance are distinct: per task,
150 reliable outcomes own items_done, while byte coordinates 1..1,500 drive
cadence with valid item/attempt identities and matching outcomes. Ordinary final
results retain the 1,500-byte attempted-work high-water; maximum-no-Gap remains
outcome-only. The active-version field overlay cannot alter the frozen v1 corpus.
The installed event diagnostic consumes this v5 shape independently of the
frozen custody corpus; a complete diagnostic run does not close current timing
acceptance.

A new or changed transport representation retains the protected contract,
artifact/validator identity, realistic corpus, source/runtime/dependency admission,
ordered 128/64/64 queues, no-Gap, cleanup and terminal witnesses. The committed
runners and artifact validators under tests remain unchanged by this migration.
PRESENTATION owns its projection/gesture budgets and HISTORY owns its query
budgets under the recorded profile. None is aggregate task-graph certification.
