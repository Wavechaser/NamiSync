# Interfaces Layer

Status: M1 Stage 5.5's process-local `interfaces/service.py` facade, reviewed
sync/history adapter, explicit inventory/baseline/verify/rebaseline commands,
semantic-settings seam, revisioned selection, opaque-id location actions,
retry receipts, typed scan warnings, and final axis-preserving result
classification are implemented. M1 Stage 1's isolated cosmetic UI-state
storage, tested WebView2 security seam, classified launchers, coordinated
database-pair facade, secured product-host composition, and the hardened
`pick_folder`/`start_plan`/`next_events`/`close_task` transport are implemented.
GUI Break 1's icon infrastructure remains implemented. Audit reopened its
token/material/motion foundation and Slice 4's visible-sequence, operable-tree,
and shell evidence for realignment; the user-facing
plan, inventory, history, and control surfaces remain, and the API remains
latent.

## Purpose

Interfaces translate user/client intent into typed workflow submissions and
render dispatcher session state, events, plans, inventory, history, and results.
They own interaction behavior, validation feedback, and presentation state—not
sync policy, filesystem mutation, SQL, plan dependencies, integrity
classification, or session lifecycle.

CLI and desktop must produce the same workflow request for the same intent and
interpret the same typed result consistently. API, when added, follows the same
rule.

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
admission failure restoring `reviewing`. Replanning resets user selection but
advances the request's revision monotonically, even when deterministic
operation ids repeat. Recognized selection command ids remain retry tombstones
across that replacement, so a lost response cannot reapply old intent to the
new artifact. Folder gestures expand only toggleable descendants; a
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
remains page-bounded.

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
through the location-scoped workflow tree: refresh carries a recursive subtree
root so it can discover new descendants, while integrity freezes the indexed
subtree to exact paths before admission. Path-based CLI calls retain their
existing full/exact behavior.
If a queued or resumed activity becomes unresolved at wake-up, its retained
`InventoryDetailsView` carries the same state/candidates and the CLI renders the
same corrective guidance. A provisional ambiguous binding exposes no selected
mount; only an actual prior explicit choice is reported as selected.

Session-creating plan, execution, inventory, and integrity commands use bounded
command-id single-flight guards around receipt lookup, mutable validation,
admission, and receipt publication. Plan retries check the original path
gesture before revalidating a filesystem that may have changed after admission;
ID-based location retry signatures likewise bind the canonical raw opaque-id
gesture and are checked before rereading mutable inventory. Different command
ids remain independently admissible; execution keeps its named `in-flight`
commitment response. Closing a retained session releases its receipt, and
receipt lookup, publication, and removal share one lifecycle gate with
dispatcher retention so neither a retry nor a late admission can return a
receipt for an already-closed session. Shutdown prevents a late admission
return from repopulating cleared receipt state; its closed transition and
receipt-map clearing take that same gate, so an in-flight replay finishes
before invalidation.

The web task boundary owns its linked observation, session, plan, and start
receipt. After the terminal record is delivered, `close_task` releases those
artifacts stepwise and removes the adapter task; delivery uncertainty reuses
one bounded retained close receipt. Live tasks are capped at 48. Retained
database history is independent and is never removed by task close.

The runtime owns `SemanticSettingsStore`; the service accepts optional
keyword-only `settings_path` but imports no database package. Its default is
`settings.json` beside the selected ledger. `read_semantic_settings()` and
`commit_semantic_settings(SemanticSettingsPatchView)` expose only primitive
workflow views: filters, deletion policy, trash-on-update, preservation
booleans, and source-casing propagation. A partial patch preserves omitted
fields. Public view construction requires exact booleans, tuple-of-string
filters, a supported deletion value, and the correct preservation view, so an
invalid patch cannot poison the atomic settings file.
`start_plan(..., deletion_policy=None)` captures the complete stored
snapshot once; an explicit deletion override changes only that plan, and
review exposes the complete frozen snapshot while commit/execution never reread
settings.

`classify_result(OperationResultView)` returns a primitive `ResultCategory`
containing the workflow-owned headline and the independent filesystem,
integrity, recording, audit, disposition, and cancellation values. The CLI
uses only that headline for its numeric exit and continues rendering every
secondary axis. It never rebuilds domain lists by attribute shape or parses a
diagnostic string.

`SessionObserver.observe(session_id, sink)` performs a synchronous
get-before-subscribe check, returns an already-terminal view without opening a
stream, and otherwise forwards only primitive session event/record views to the
sink. Its worker blocks on `EventStream.next()` without polling, recovers an
ejected stream from the first undelivered sequence, and never exposes the raw
stream. Slice 3 adds an explicit positive-first-desired-sequence resubscribe
seam. Plan start may transactionally adopt a preopened stream before `PENDING`
and schedulable publication; that sink is excluded from receipt identity, and
attach failure or a shutdown race rolls back the unpublished session and starts
no work. Unsubscribe closes every stream before joining its worker. Service
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

`interfaces/ui_state.py` owns strict-shape `ui-state.json` independently
from database-owned semantic defaults. It retains at most five source and five
target recents separately, deduplicates Windows spellings, and stores only
cosmetic window/column/sort mappings. Atomic replacement prevents torn JSON;
cross-process semantic write coordination deliberately remains in the database
settings store.

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
NamiSync application code never constructs JavaScript or calls `evaluate_js`,
`run_js`, or `Window.state` to carry application data. Pinned pywebview does
construct JavaScript internally for its exposed-function return transport;
its escaping is therefore inside the tested security boundary, not evidence
that the transport is system-wide script-free. The implemented host preserves
the NamiSync-owned shape and strict shared text sink; Slice 3 implements the
bounded/coalesced event drain, while Slices 5 and 6 add the production plan and
inventory DOM renderers.

The sole presentation-only native-to-page path is a fixed revisioned system
appearance envelope posted through WebView2 after native origin/security
attachment. Its packaged receiver validates the complete schema and may update
only fixed root appearance datasets and CSS custom properties. It exposes no
browser-to-native sender, command, URL, path, HTML, or dynamic property name and
therefore does not widen bridge authority.

GUI Break 1's icon helper is presentation-only and never becomes another bridge
or asset-authority surface. It resolves one exact visual glyph name through a
frozen source-owned `icons.js` registry to fixed inert CSS classes. Those
classes select package-local CSS-mask SVGs and inherit `currentColor`; no view,
payload, command, or returned string can supply markup, a class, URL, path, or
registration. Unknown names and sizes are refused before DOM mutation.

The current production table contains exactly four rows. Slice 2 owns
`pick_folder` and `start_plan`; the former owns one native user interaction and
returns `null` or an opaque purpose-bound slot id plus inert display text; the
latter accepts only one source slot, one target slot, an explicit
`null`/`trash`/`additive` deletion choice, and a gesture `command_id`, then
delegates to `NamiSyncService.start_plan`. The browser never supplies a path as
authority. `commands.py` owns immutable command rows and exact payload
validation, `bridge.py` owns the v1 envelope/primitive codec/refusal boundary,
and `slots.py` owns the locked 32-entry, 30-minute process-local path table.
The exact envelopes, ids, messages, deadlines, and retry rule are normative in
`M1_SHELL.md`. `assets/bridge.js` is the only `window.pywebview` owner and
`assets/render.js` is the strict production `textContent` sink. Production has
no runtime command registration: the headed gate adds `test_report` only by
constructing a private immutable mapping under `tests/`, and that row and page
are absent from the wheel.

Slice 3 owns `next_events`, and implements adapter-owned
`task-<32-lowercase-hex>` identity; task ids never enter the task-agnostic service
or dispatcher. `start_plan` adds that task id to its web result and replays it
with the same command receipt. `next_events` returns at most 64 exact
event/record tagged updates from one 64-entry task queue. Progress may replace
progress or yield to reliable data; reliable updates never displace one another
and backpressure until drain or close. One server drain per task waits at most
25 seconds under a 30-second browser deadline. Only transport/protocol
uncertainty resubscribes after the last accepted event; explicit `Gap` remains
visible, stops later ordinary-batch updates, and resubscribes from its
`first_missed_seq`. A matching leading gap in that recovery result proves the
prefix unavailable and permits the retained tail without looping; numeric holes are legal progress
coalescing. Terminal plan sessions cease being live/active-rail work but remain
task-owned recovery authority until task close.

Audit hardening adds only `close_task`. The registry requires terminal-record
delivery before release and retains at most 48 same-payload close receipts.
Exact `start_plan` wire intent is checked before volatile slot resolution, so a
lost response remains replayable after slot expiry. The browser policy is an
exact tested mirror of Python metadata; drain recovery and release retry have
finite delayed budgets. Bridge handler admission is capped at 64, with a fixed
`bridge_busy` refusal.

Slice 4 adds presentation only and does not change that table. A typed
structural view and pure functions in `visible_sequence.py` validate one workflow-owned
pre-order array and derive collapse/search/caller-filter retention, exact
1..256 windows, and indexed deepest-visible ancestor anchors without retaining
a view, duplicating the full workflow array, or importing domain policy. Search
accepts at most 65,536 UTF-8 bytes before traversal; external request limits
remain boundary-owned. The installed `tree.js` consumes only
`{offset,total,rows}`, renders at most 256 operable 28-pixel rows between two
fixed spacers through the inert text sink, and rejects stale generations. Its
single-tab-stop focus model consumes server-derived parent/child/sibling
metadata. Structural task/work landmarks are labelled but not focus targets;
the transparent rail and inactive task-card surface expose Mica. BR-G-34 and
SH-G-7 remain reopened until direct workflow-node, scale, keyboard/platform
accessibility, geometry, and clean-wheel evidence passes. Slices 5 and 6 remain the first owners of domain
projection commands and real rows.

Pywebview reinjects its bridge after every `NavigationCompleted`, including
canceled or failed navigation, and rebuilds its in-flight return-callback
table. The renderer can trigger this repeatedly. Frontend initialization must
therefore treat `pywebviewready` as repeatable and idempotent, install no
duplicate listeners, and ensure exactly one `next_events` request is re-armed
per task after every firing. A lost mutation response retries with its
original `command_id`; a lost drain resumes from the last accepted sequence
and reconciles through terminal truth.

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
renderer-checked initialized callback. The host snapshots the exact four-row
production mapping before exposing the page. Loaded attachment failure
destroys the window once; pre-native initialization failure does not call
destroy. One finalizer closes any constructed service, then releases logging,
app-path leases, and the mutex only after complete quiescence, preserving the
initiating startup diagnosis.
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

- Bound each complete externally supplied request at ingress. The desktop
  bridge's ceiling is 65,536 UTF-8 bytes including its JSON envelope; a future
  REST, IPC, or other adapter must impose an equal-or-stricter whole-request
  limit before constructing internal presentation values.
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
- Commit only after the plan session terminates, binding plan fingerprint and
  exact selection digest. Never expose an “execute anyway” path around
  commitment or fresh preflight.
- Runtime thread/ownership guards raise real exceptions, not `assert`.

## Shared Actions

An interface action has one source of truth for label, enablement, shortcut,
scope, confirmation, and dispatch. Menus, buttons, context menus, and commands
adapt that action rather than duplicating rules. Enablement is derived from
typed state and selected scope; hidden/filtered selection is disclosed.

Presentation logic that selects a row, computes scope, or builds a result model
is testable without entering a modal event loop.

## Session And Worker Boundary

Dispatcher is the lifecycle source of truth. A desktop may need toolkit threads
to keep its event loop responsive, but those adapters do not invent another
domain session state machine or own volume locks. Worker release is identity-
checked, result delivery is marshaled to the UI thread, and close waits for
actual thread/session completion without blocking the event delivery needed to
complete it.

## Security And Data Isolation

Explicit database overrides reach both ledger and history. Tests never default
to real `%LOCALAPPDATA%` databases. Paths and annotations are treated as data;
no shell interpolation, HTML injection, or spreadsheet formula execution is
introduced by rendering/export.

Read-only commands/views may coexist with active writers under WAL. Mutating
interfaces use the same dispatcher and physical-volume custody; GUI single
instance is a presentation-instance rule, not a global ban on safe CLI work.

## Latent API

The future API exposes versioned request/result/event schemas, authentication,
local binding by default, explicit replay gaps, and no direct module endpoints.
It is not scaffolded until a concrete client exists; core event schema version
is the provisioning seam.

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
- Location commands bind exactly one explicit root or retained id before
  submission; ambiguity requires a listed mount, and no mapping role is
  inferred.
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
