# Desktop UI

Status: M1 Stage 6 design and delivery contract. M1 Stages 1–5 provide the
desktop's service, view, settings, session-observation, and bridge-security
seams; no headed desktop host or frontend has shipped yet.

## Purpose

NamiSync's Windows desktop is a local, headed adapter for reviewing and
controlling safe one-way mirroring, location inventory and integrity work, and
retained history. It makes the workflow's existing facts comprehensible; it
does not decide sync policy, calculate plans, write SQLite, mutate files, or
own a second session lifecycle.

The Stage 6 target is a `pywebview` host forced to Edge Chromium/WebView2 with
packaged web assets. The earlier PySide6 proof-of-concept is historical input,
not the implementation target or test contract. `ui_mockup/mockup.html` is the
starting frontend artifact to revise into the packaged UI.

## Scope and delivery boundary

Stage 6 delivers:

- a `nami-sync-gui` desktop entry point and a no-subcommand desktop launch;
- one single-instance desktop shell, task rail, work area, plan review,
  inventory view, and history dialog;
- desktop actions for reviewed sync, inventory, baseline, verify, rebaseline,
  semantic settings, and pause/resume/cancel where the registered activity
  supports them; and
- the WebView2 bridge, static-asset packaging, security controls, and frontend
  tests needed to make those views safe to use with hostile filesystem names.

It does not add durable plan or session storage, cross-process task visibility,
general migration, history retention, unattended execution, a settings CLI,
or a new workflow API. Session and saved-plan state are process-local in M1:
closing the desktop loses unexecuted plans and restart-resume is not promised.

## Adapter boundary

The desktop imports only `NamiSyncService` and its primitive workflow views.
It must not import `core`, `modules`, `db`, CLI internals, or construct a
dispatcher, runtime, workflow request, repository, or recorder.

The service already provides the desktop's command surface:

```python
start_plan(source, target, *, deletion_policy=None) -> PlanSession
start_execution(request_id, *, verify_after_execute=False) -> ExecutionSession
start_inventory(...), start_baseline(...), start_verify(...), start_rebaseline(...)
read_semantic_settings() -> SemanticSettingsView
commit_semantic_settings(patch) -> SemanticSettingsView
```

`SessionObserver.observe(session_id, sink)` supplies primitive current-state
and event/record views. The desktop owns the bounded presentation queue fed by
that sink; it does not expose raw dispatcher streams to JavaScript. It must
unsubscribe on task close and close every observation before service shutdown.
`classify_result()` supplies the single headline and independent filesystem,
integrity, recording, audit, disposition, and cancellation axes. The frontend
renders those facts; it never reimplements headline precedence or parses
diagnostic text.

Location commands bind one explicit root or retained location id before
admission. `LocationResolutionError` already carries the five visible states
(`resolved`, `offline`, `ambiguous`, `root_missing`, `root_unavailable`), exact
candidate mounts, and corrective detail. The UI must request a user-selected
mount for ambiguity rather than inferring one from a mapping or prior task.

Semantic settings and UI state are deliberately separate. Semantic settings
are read and partially committed through the facade, then captured immutably
by planning. `ui_state.py` owns only cosmetic recents, geometry, columns, and
sorting in `ui-state.json`; it must not become another semantic-settings or
session store.

## Bridge and renderer security

The host exposes exactly one JavaScript-facing method:

```text
dispatch(command_json)
```

It remains versioned, JSON-schema-shaped, size-bounded, and command-allowlisted
through `BridgeDispatcher`. Commands and responses use opaque ids and primitive
structured data, never raw filesystem paths as authority. The frontend starts
every request and receives structured return values; host-initiated
`evaluate_js`, `run_js`, and `Window.state` are forbidden application-data
channels.

Live state uses one bounded, coalescing `next_events` pull/drain request. The
host preserves reliable item and terminal ordering, allows replaceable progress
snapshots to collapse, and makes a gap or disconnected task visible instead of
inventing history. A JavaScript call must never block indefinitely waiting for
an event, and the frontend must keep at most one outstanding event drain per
task.

The host must force `gui="edgechromium"` and fail with an install action if the
Microsoft Edge WebView2 Runtime is unavailable; silent MSHTML fallback is not
acceptable. Before startup the host registers an `initialized` callback. Once
the static asset server has selected its random loopback port, that callback
derives the exact origin from `window.real_url` and registers an idempotent
synchronous `before_load` callback. On the WinForms UI thread `before_load`
reaches `CoreWebView2` and attaches the tested `NavigationStarting`,
`NewWindowRequested`, and `SourceChanged` handlers exactly once before
application calls are exposed; setup and dispatch workers never access the
UI-affine native object. Navigation outside the exact packaged asset origin is
canceled and every popup is handled/canceled.

`dispatch` independently rechecks a lock-protected snapshot of the native
committed `CoreWebView2.Source` on every call. It does not authorize from
pywebview's managed `Source` or `get_current_url()`: both can report a rejected
navigation target after WebView2 canceled it and retained the packaged
document. A canceled request leaves the snapshot unchanged, while a genuinely
committed off-origin source replaces it and causes dispatch to fail closed.
The packaged static-asset server is not an API or event channel.

The frontend uses a restrictive CSP and DOM APIs such as `textContent` for all
filesystem-derived data. It must never use `innerHTML`, build executable script
from returned data, or interpolate a filename into an attribute, URL, command,
or bridge request. Hostile-name fixtures are required end-to-end.

## Interaction contract

The task rail is a presentation grouping over live service sessions and
retained history, not a new durable task model. It shows activity kind, source
and target when applicable, current phase, progress, and a truthful terminal
headline. Subject-only activities do not fabricate a source-to-target label.
Closing a terminal task drops only its live presentation state; retained
history remains. Closing queued or busy work asks for the service-supported
control, waits for actual terminal observation, and never treats a transient
progress flag as completion.

Sync remains a two-session interaction: plan first, review its immutable
fingerprint-bound intent, choose a dependency-closed selection, type the exact
confirmation, then start execution with fresh preflight. Editing selection or
plan-affecting options requires a new commitment. There is no execute-anyway,
auto-commit, or unattended path. `verify_after_execute` is an explicit option;
when selected, the one execution session may return ordered operation and
integrity items plus ordered phase summaries.

Plan review shows executable operation ids, dependencies, reasons, source and
destination, bytes, evidence, conflicts, blocks, and deferred outcomes. A
folder or rename grouping is presentation only and never turns into a hidden
directory mutation. The UI distinguishes refusal, all-noop, partial, canceled,
failed, mismatch, verification-incomplete, and recording/audit degradation
from the typed result axes rather than color or byte totals alone.

Inventory is retained state distinct from plan state. Its location scope,
completeness, observed/missing counts, presence, and evidence come from
`InventoryDetailsView` and `InventoryRowView`. Refresh, baseline, verify, and
rebaseline reuse one action definition across buttons and context menus.
Selected paths are exact root-relative scope; rebaseline always asks for its
explicit acceptance intent. A context action first establishes a valid target
row, and blank space targets nothing.

History uses retained activity-aware envelopes and details. It exposes all four
truth axes and ordered items/phases, including compound execute-to-verify runs.
Restoring a prior run means starting a fresh plan; history is not a replay or
resume surface.

## Presentation and responsiveness

Progress is replaceable telemetry. The UI updates current path, copied bytes,
item counts, and phase without assuming a throughput estimator exists. Executor
pipeline diagnostics are opt-in developer data, not the rolling transfer rate
or ETA promised to users. Filter/search state never changes the underlying
plan or inventory selection; changing a location or plan option invalidates
only the state that semantically depends on it.

Use accessible text and non-color outcome cues, stable layouts, and full-path
accessibility text for elided paths. Empty, unavailable, ambiguous, blocked,
and failure states must say what the user can do next. Dark/light presentation
details may evolve, but contrast and no-color-only signaling are requirements.

## Acceptance criteria

- A desktop request produces the same facade call, primitive views, result
  classification, and mandatory sync review as the CLI.
- The app starts only with Edge Chromium/WebView2, blocks external navigation
  and popups, rejects off-origin dispatch, and transports no application data
  through executable JavaScript text.
- A bounded coalescing event drain preserves reliable item/terminal ordering,
  makes gaps visible, and closes all observations cleanly on task close and
  app shutdown.
- Hostile filenames remain structured data and render as text, never HTML or
  executable content.
- Plan, inventory, settings, and history consume facade views only and remain
  semantically separate; UI cosmetics never change a plan's captured settings.
- Busy, paused, canceled, refused, partial, degraded, mismatch, and compound
  verification outcomes are truthful and distinguishable without parsing
  strings or inferring status from bytes.
- Tests cover exact confirmation, location ambiguity, opaque-id authority,
  duplicate/out-of-order bridge responses, event-gap recovery, context target
  selection, process-local restart limits, and one-instance behavior.
