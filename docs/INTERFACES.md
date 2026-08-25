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
BR-G-45 terminal-artifact
retention and shell-owned SH-G-15 whole-runtime containment remain independently
open.
GUI Break 1 and Slice 4 completed their audited realignment and were hardened
and reverified on 2026-08-17; the user-facing
Setup, plan, inventory, integrity, and control surfaces remain. The history and
global-settings pages are deferred by the accepted second-half reslice. The gated desktop bridge
API and production mapping are active, while the current empty product page
invokes only startup and has no later workflow-surface callers yet.

Stage 6 checkpoint 3.2 has activated the exact event-v5, scalar, recording, and
database-epoch boundary. Native directory admission, complete Setup, process-
live desktop tasks, compact artifacts, and bounded evidence reads remain later
checkpoint targets. Exact cutovers live in [M1_BRIDGE.md](M1_BRIDGE.md);
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

`interfaces/service.py` owns one process-local `LocalWorkflowRuntime`, the
domain-blind dispatcher, the exact six-kind registration table, sync
plan/review/commit sequencing, history access, controls, and primitive workflow
views. Runtime plan storage remains the existing process-local dictionary behind
named `save_plan`/`get_plan`/`drop_plan` methods; it is not a `PlanStore` and
does not survive process exit.

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

The current public service surface includes:

```python
NamiSyncService(ledger_path, history_path, *, settings_path=None)
validate_database_contracts() -> DatabaseContractView
initialize_database_contracts() -> DatabaseContractView
start_plan(source, target, *, deletion_policy=None, command_id=None,
           observation_sink=None) -> PlanSession
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

### Stage 6 second-half service target

Exact wire, scalar, task-authority, population, and retention contracts live in
[M1_BRIDGE.md](M1_BRIDGE.md) and [DEFENSE.md](DEFENSE.md).
The event/scalar/persistence subset is active from checkpoint 3.2; task
authority, population retention, and product-surface rows activate only in
their named later checkpoints.

Workflow owns parsing, fresh admission, and canonical Setup; the adapter owns
only bounded intent slots and recomputed recent-location handles. Every desktop
session adopts observation before schedulability. Its process-live task binds
at most one current session, retains orthogonal named generations, and keeps a
published H2 plan immutable without inventing domain lifecycle or volume locks.

Only complete review generations and compact overlays become task state.
Terminal reconciliation repairs delivery gaps; full result items and transient
hashes never enter JavaScript. Server projections own hierarchy, scope, paging,
and framing. Task reads rehydrate the UI, exact release removes session custody,
and close destroys task presentation/receipts. Interfaces follow and recheck
bridge authority around outside work.

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

The currently implemented session-creating plan, execution, inventory, and
integrity commands use bounded command-id single-flight guards around receipt
lookup, mutable validation, admission, and receipt publication. Plan retries
check the original path gesture before revalidating a filesystem that may have
changed after admission; ID-based location retry signatures likewise bind the
canonical raw opaque-id gesture and are checked before rereading mutable
inventory. Different command ids remain independently admissible; execution
keeps its named `in-flight` commitment response. In the current session-oriented
implementation, closing a retained session releases its receipt, and receipt
lookup, publication, and removal share one lifecycle gate with dispatcher
retention. The accepted task target moves desktop receipt lifetime to explicit
task close so plan and later-session replay remain recoverable after terminal
session release; session-exact release removes only dispatcher/observation
authority. Shutdown still prevents a late admission return from repopulating
cleared receipt state, and close-receipt tombstones remain bounded.

The web task boundary owns its linked observation, zero-or-one current session,
retained plan and pane artifacts, revisions, reservations, and receipts.
`M1_BRIDGE.md` exclusively defines terminal-session release, explicit task
close, receipt convergence, and the count/byte capacity exposed through the
bridge. Plan task records retain the workflow's exact `sync-plan` kind across
the service and browser boundary; the adapter does not rename it. Retained
database history remains independent of adapter task cleanup.

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
stream. Slice 3 adds an explicit positive-first-desired-sequence resubscribe
seam. The currently implemented plan start may transactionally adopt a
preopened stream before `PENDING` and schedulable publication. The accepted
target makes that path mandatory for every desktop session start. In both forms
the sink is excluded from receipt identity, and attach failure or a shutdown
race rolls back the unpublished session and starts no work. Unsubscribe closes
every stream before joining its worker. Service
shutdown closes all observer streams and joins all observer threads before
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

The replacement for the unused `interfaces/ui_state.py` prototype now owns
strict-shape `ui-state.json` independently from database-owned
semantic defaults. Schema v1 contains only the typed appearance section and
its `system`, `light`, or `dark` value. Ledger-derived recents never enter this
file; geometry, column, sort, treegrid expansion/grouping, and filter state
require later typed schema additions.
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
currentness-checks, and posts production WebView2 messages. Appearance and
readiness share that sink without sharing domain state.
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
read, allowing a healthy new document to converge a late prior-document
mutation without widening the bridge.

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
`window.pywebview`. At the accepted location-admission checkpoint, workflows
own path parsing, probing, and candidate classification; a slot never becomes a
second path-policy authority.

The explicit-`Gap`-only recovery and command-specific `start_plan` revision
decisions are ratified and their named regressions have landed. Numeric holes
alone are not recovery signals. Browserless/Node probes remain supplemental
except for the ordinary non-skippable drain-manager Progress validator/replay
gate, which resolves `NAMISYNC_TEST_NODE` before `PATH` and owns atomic batch
rejection plus clean replay. The remaining named browser-behavior witnesses
run through the installed production bridge and renderer in real WebView2.
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
method. The
synchronous WinForms callback only claims one worker and vetoes; that worker
  performs reject, close/wake, wait, task-observation unsubscribe, and service
close in order. Window-owned appearance remains subscribed during every
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

Dispatcher remains each session's lifecycle truth. The adapter task serializes
attachment and retains presentation without owning volume locks or rewriting
dispatcher/history truth. Publication faults follow the bridge protocol, and
queued events cannot repopulate discarded provisional state. Toolkit worker
release is task/session-checked, delivery is marshaled to the UI thread, and
close waits without blocking the terminal record needed to finish.

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

## Acceptance Criteria

- Import-linter proves interfaces import workflows/dispatcher but not
  core/modules/db directly under the agreed composition-root arrangement.
- Equivalent CLI/desktop requests produce equivalent workflow payloads and
  result classification.
- Current CLI location commands bind exactly one explicit root or retained id
  before submission; ambiguity requires a listed mount, and no mapping role is
  inferred. The accepted desktop target instead supplies a purpose-bound slot
  earned through the common picker/typed/recent admission service and freshly
  re-admits it at every real start.
- Semantic settings read/partial-commit views contain primitives only; planning
  captures one immutable full snapshot and a deletion override changes no other
  field.
- No interface mutation path bypasses dispatcher, mandatory review, preflight,
  executor, or recorder.
- Invalid/unusable paths show a specific next action rather than silently
  disabling everything.
- Refused zero-op, all-noop, partial failure, cancellation, mismatch, and
  ledger-behind states render distinctly.
- Audit-behind is independent of ledger-behind; queued discard renders from
  `CANCELED+UNRUN`, not byte count or free-form reason.
- Event reconnect handles current state/tail/gap without duplicate row outcomes.
- Explicit unsubscribe, window close, and service shutdown close blocked event
  streams before joining observer threads.
- Changing plan selection after review invalidates commitment; neither UI nor
  CLI can submit the stale commitment.
- Action source-of-truth tests cover menu/button/context presentation equality.
- Presentation-selection tests run without modal loops or live filesystem/DB.
- Thread/result callbacks execute on the required presentation thread and raise
  explicit runtime errors on violation even under `python -O`.
- Database override tests write neither ledger nor history to real user paths.
- A ledger override selects its sibling `settings.json`; malformed settings
  refuse planning before dispatcher submission.
- Read-only history remains usable during an active mutating session.
- History summaries avoid event decoding; item/event pages enforce the
  256-record decoded/returned ceiling and stable-watermark traversal, sparse
  event bounds use one indexed lookahead, and incomplete rows never render as
  terminal or resumable work.
- The security spike forces Edge Chromium, attaches both native navigation
  guards, rejects a dispatch after hostile navigation, and exposes only the
  versioned allowlisted structured endpoint.
- Stage 6 interface tests cover task rehydration, immutable generations,
  server-owned trees, shared admission, and guarded evidence; exact gates live
  in [M1_BRIDGE.md](M1_BRIDGE.md), checkpoint coverage in
  [M1_SHELL_H2.md](M1_SHELL_H2.md), and test-scope policy in
  [TESTS.md](TESTS.md).
