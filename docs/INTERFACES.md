# Interfaces Layer

Status: M1 Stage 5.5's process-local `interfaces/service.py` facade, reviewed
sync/history adapter, explicit inventory/baseline/verify/rebaseline commands,
semantic-settings seam, revisioned selection, opaque-id location actions,
retry receipts, typed scan warnings, and final axis-preserving result
classification are implemented. M1 Stage 1's isolated cosmetic UI-state
storage and tested WebView2 security spike remain the desktop foundation; the
desktop host remains Stage 6, and the API remains latent.

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

`start_execution(request_id, *, verify_after_execute=False,
expected_revision=None, destructive_acknowledged=False, command_id=None)`
preserves the untouched M0/CLI default and opts into the Stage 4
execute→verify workflow only when requested. An omitted revision is valid only
for pristine revision-zero selection. Edited review state requires the current
revision; commitment transitions `reviewing → committing → committed`, with
admission failure restoring `reviewing`.
Only the execution registration supplies
`settle_canceled=runtime.settle_canceled_execution`; the service does not decode
continuations or decide cancellation policy. Retained `HistoryRunView` exposes
primitive filesystem/integrity/recording/audit axes, disposition, cancellation,
headline, ordered items, and ordered phases, using the same workflow
classification source as live result views.

The current public start/settings surface is:

```python
NamiSyncService(ledger_path, history_path, *, settings_path=None)
start_plan(source, target, *, deletion_policy=None, command_id=None) -> PlanSession
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
```

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
stream. Unsubscribe closes every stream before joining its worker. Service
shutdown closes all observer streams and joins all observer threads before
dispatcher shutdown, then closes the workflow runtime last so audit finalization
cannot reach a closed history store.

`cli` and `web` occupy one import-linter layer above `service`: neither adapter
may import the other, and the service may import neither adapter. The
`interfaces` package initializer preserves its public `main` entry point through
a lazy wrapper, so importing the package or future web host does not import the
CLI adapter until that function is actually invoked.

## M1 Stage 1 Desktop Foundations

`interfaces/ui_state.py` owns strict-shape `ui-state.json` independently
from database-owned semantic defaults. It retains at most five source and five
target recents separately, deduplicates Windows spellings, and stores only
cosmetic window/column/sort mappings. Atomic replacement prevents torn JSON;
cross-process semantic write coordination deliberately remains in the database
settings store.

`interfaces/web/security_spike.py` proves the security-sensitive host shape
without shipping a desktop or adding a pywebview dependency. Startup explicitly
requests `gui="edgechromium"` and turns only pywebview's renderer-unavailable
failure into an actionable WebView2 message. Once the native control exists,
the spike attaches `NavigationStarting` and `NewWindowRequested` handlers on
`CoreWebView2`, cancels every popup, and cancels navigation away from the exact
packaged scheme/host/effective port.

The only public bridge method is versioned, size-bounded, allowlisted
`dispatch`. It rechecks the current exact origin on every call, accepts one
strict JSON request object, and returns a JSON-safe structured result. There is
no `evaluate_js`, `run_js`, or `Window.state` data path. The actual Stage 6 host
must preserve this shape and add the bounded/coalesced event drain plus escaped
DOM rendering.

## Common Adapter Contract

- Validate syntax/presence early and report actionable path/input errors; domain
  validation remains in workflow/preflight.
- Submit through dispatcher/registry rather than starting ad hoc workers that
  call modules directly.
- Read current session records and observe through the service's sink API.
- Treat progress as a replaceable snapshot. Handle bounded state/item/terminal
  delivery, including `Gap` plus resubscription for an ejected/late ordinary
  subscriber; history has timeout-bounded admission delivery and exposes failure
  through the audit axis rather than pretending the stream was complete.
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
- The security spike forces Edge Chromium, attaches both native navigation
  guards, rejects a dispatch after hostile navigation, and exposes only the
  versioned allowlisted structured endpoint.
