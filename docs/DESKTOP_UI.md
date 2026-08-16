# Desktop UI

Status: M1 Stage 6 design and delivery contract. M1 Stages 1–5.5 provide the
desktop's service, view, settings, session-observation, and bridge-security
seams. The classified launchers, wheel-packaged bootstrap assets, secured
product-host composition, and the production transport defined by
`M1_BRIDGE.md` now exist. Ordinary and installed-wheel evidence covers host
isolation, runtime refusal, popup/navigation guards, single-instance behavior,
native picker path confinement, committed-origin refusal, hostile text, and
logging privacy. The named browser-behavior witnesses now run through the
installed production bridge and renderer in real WebView2. Slice 3 evidence
covers transactional observation, bounded drain behavior, recovery, and
repeated bridge readiness. The fixed, non-sliding 150 ms progress-only linger
and its immediate reliable/lifecycle wake regressions have landed. An active
long poll may hold the first detailed progress snapshot for the full interval;
receipt and reliable running-state feedback bypass that linger. Benchmark
accounting now streams bounded browser/producer evidence, performs final
assembly after the child exits, and labels whole-runtime memory as a
non-acceptance diagnostic; its event pass alone is not SH-G-8 custody closure
authority. The accepted independent custody evidence below supplies closure.
The frozen/disjoint realistic corpus and production-path runner have also
landed, including exact real-deque 128/64/64 no-`Gap`, terminal path-cut,
cleanup, and clean source/dependency/runtime/digest-authority witnesses. The
committed calibration-a artifact records normative ordinary/exact-maximum
transport measurements, the separate contract freezes the 1,966,080-byte
ceiling, and three fresh holdout-b runs pass at 1,351,794 ordinary and 1,513,014
exact-maximum bytes. This closes SH-G-8 and BR-G-42 event/transport custody
only. A separate current-source one-child guard now requires both live custody
shapes to remain within that frozen ceiling on ordinary suite runs;
BR-G-45 separately leaves full terminal-artifact retention open, and
shell-owned SH-G-15 leaves version-bound whole-runtime containment open. The
earlier whole-Job delta is diagnostic input only, not a result for any of those
new predicates. GUI Break 1
and Slice 4 have completed their audited token/material/motion and
visible-sequence/tree/shell realignment with ordinary, scale, and real
clean-wheel headed evidence. User-facing plan, inventory, history,
and control surfaces remain; `M1_SHELL.md` owns their implementation order and
beta-package closure.

`M1_BRIDGE.md` is the sole normative authority for bridge envelopes, commands,
errors, retry/revision identity, sequence and terminal lifecycle, and BR-G
acceptance gates. This document owns the user-facing and visual contract; it
does not restate the wire protocol.

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

- a `nami-sync-gui` GUI-subsystem entry point with no retained console window;
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

## Packaging and local host state

The console and desktop entry points deliberately remain separate Windows
subsystems over one implementation. `nami-sync` and `python -m namisync` always
route through `interfaces/launcher.py` to the CLI; with no subcommand they print
usage, point to `nami-sync-gui`, and exit with the existing usage status.
`nami-sync-gui` resolves its one path authority, then lazily imports the web
host. The host acquires the fixed per-logon instance mutex before creating any
directory or logger; only the primary configures file logging and imports
pywebview. Explicit CLI work never imports or initializes pywebview.

NamiSync remains version `0.1.0` until M1 is complete. The runtime `VERSION`
alone supplies project/package metadata, logging, protocol-independent version
checks, and later frozen-file metadata. `NICKNAME` is `Gertrud` and is only a
human-facing label for About, release notes, and changelog headings; it never
enters filenames, databases, mutexes, CLI behavior, protocols, or compatibility
logic. The host stack pins pywebview 6.2.1 and pythonnet 3.1.0;
Bottle has a floor of 0.13.4, the reality-tested server version. NamiSync uses
pythonnet's default Windows .NET Framework (`netfx`) runtime and refuses a
conflicting runtime override. The existing read-only .NET Framework check is
therefore also the pythonnet prerequisite check.

One host-owned path set places production data under
`%LOCALAPPDATA%\NamiSync`: databases/settings/UI state at the root, rotating
UTF-8 logs under `logs`, and persistent WebView2 user data under `webview2`.
The GUI-only `--data-dir PATH` option accepts an absolute local root for tests
and isolated runs; it must relocate every artifact together.
The `namisync` and `pywebview` loggers share the file handler, which is installed
before pywebview import. Pywebview starts with `private_mode=True` and the
explicit `webview2` storage path; browser state never becomes plan, task, or
filesystem authority.

Before window creation, the primary host constructs the service and consumes
the shared database-pair facade. Fresh state initializes ledger then history;
ready state continues; refused state runs the bounded finalizer and shows the
coordinated reset action through the stable native startup dialog. It then
resolves `index.html` from package resources, creates one pending native
document and a dispatcher snapshotted from the production command mapping
defined exclusively by `M1_BRIDGE.md`, and starts only Edge Chromium with
the packaged page served on a random loopback origin. The initialized callback
binds that exact origin once. Renderer/origin failure aborts before native
window creation; guard/load failure destroys the created window exactly once.
Both paths close the service, logging, and mutex without replacing the original
failure diagnosis.

Native test and gallery compositions may supply an existing absolute physical
local index file directly to `run_desktop`. The production launcher never
exposes that construction-only seam through arguments, environment, page data,
or bridge traffic, and the test page is never package data.

Frontend assets are setuptools package data and use plain same-origin ES
modules. At Slice 2 closure the wheel contained exactly `index.html`, `app.css`,
`app.js`, `bridge.js`, and `render.js`; `render.js` owns the strict
`textContent` sink. GUI Break 1 adds exactly `tokens.css`, `components.css`,
`icons.js`, `appearance.js`, four pinned local SVGs, and their `SOURCE.json` and `LICENSE.txt`
records under `assets/icons/`. The component-gallery scenario remains test-only
and absent from the wheel.
There is no npm, framework, bundler, transpiler, source map, inline script, or
inline event handler. The first running shell and installed-wheel
proof precede PyInstaller work. The frozen specification, dependency lock, CI,
third-party notices, and exact-source release material close in the final beta
packaging slice.

GUI Break 1, scheduled after Slice 3 and before production surfaces begin,
establishes the completed design-token foundation. NamiSync presents as a
Fluent 2 Windows 11 app using Segoe UI Variable for body text and
Cascadia Mono/Consolas for paths and hashes. It retains the standard native
frame. Mica is the whole-window base, with transparent page/controller
backgrounds and opaque Fluent cards for readable scrolling content; high
contrast, unavailable material, or a transparency failure falls back to an
opaque system-appropriate neutral surface. M1 adds neither Acrylic nor a
custom caption.

`tokens.css` is the only source file allowed to contain these exact 13 authored
red/green/blue/yellow/purple palette primitives:

```css
--palette-red-main: #EE6666;
--palette-red-dark: #551111;
--palette-red-light: #FFAACC;
--palette-green-main: #33DD99;
--palette-green-dark: #004422;
--palette-green-light: #99EEDD;
--palette-blue-main: #33AAEE;
--palette-blue-dark: #002255;
--palette-blue-light: #99CCFF;
--palette-yellow-main: #FFDD44;
--palette-yellow-dark: #553300;
--palette-purple-main: #BB88EE;
--palette-purple-dark: #331155;
```

Yellow and purple deliberately have no authored `light` input in the current
foundation.
A future hardcoded or derived color value is possible only after an explicit product-
author design decision and a same-change contract/token/evidence update; it is
not silently synthesized by a renderer. `tokens.css` also owns meaning-named
semantic aliases for statuses and operation categories; neutral roles use a
pinned Microsoft Fluent light/dark subset and interactive accent roles use the
observed Windows `Accent`, `AccentLight1`, and `AccentDark1` palette. These
externally owned design inputs are tested separately from the 13
NamiSync-authored primitives. The neutral and scale values are transcribed from
pinned `@fluentui/tokens@1.0.0-alpha.24` source at commit
`32b42a5bf79c1836047dfc7fae07b1320731bce4`; exact source hashes are retained
in test fixtures and accessible stroke roles own visible control boundaries.
`components.css`
consumes only those aliases for badges, banners, status pills, progress
indicators, and related controls; Slice 4-7 renderers consume
component/semantic contracts and contain
neither raw color literals nor direct palette references. The component gallery
settles light/dark mappings with visual and numeric contrast evidence rather
than inferring theme roles from swatch names. Forced colors use Windows system
colors, and text plus icon/shape/state cues keep every status understandable
without color. The gallery resolves production HTML/CSS from a clean installed
wheel and records exact installed `tokens.css`/`components.css` bytes; its own
page remains tests-only. Computed pairs must reach 4.5:1 for normal text and
3:1 for large text and non-text UI indicators/boundaries.

The same break establishes only the icon infrastructure, not the later surface
icon vocabulary. Four regular 20 px Microsoft Fluent System Icons are vendored
locally from `@fluentui/svg-icons@1.1.334` with exact package/file URLs,
per-file SHA-256 hashes, and license. A frozen
`icons.js` registry maps visual glyph names to fixed component classes; the
classes use fixed local CSS masks painted with `currentColor`. `tokens.css`
owns exact 16/20/24 px `sm`/`md`/`lg` icon sizes and `components.css` owns
alignment and states.
There is no remote load, icon font, runtime registration, inline/generated SVG,
or data-derived class/asset path. Icons remain decorative beside visible text;
icon-only controls require their own accessible name. Later slices extend the
fixed set only when their real controls make a glyph necessary.

Native appearance observes Windows light/dark/high-contrast state and live
`UISettings` `Accent`, `AccentLight1`, and `AccentDark1` values. A fixed
revisioned envelope reaches packaged `appearance.js` through UI-thread
`PostWebMessageAsJson`; only its exact schema and fixed CSSOM sinks are valid.
Observation subscribes before its mandatory initial read. Later native events
advance one coalesced generation whose current state is read and applied on the
window UI thread; a newer generation is deferred to another UI turn so stale
callback-thread snapshots cannot become newest or starve the message pump.
Opaque fallback requires sufficient structured backdrop/glass/form/controller
landing evidence. A live reapply that confirms neither native path publishes
`degraded`, which returns the page itself to its theme-correct opaque base;
startup still refuses an initially unconfirmed material. Appearance remains
subscribed through incomplete or exceptional close attempts and closes once
only after complete service close, before destruction. Shared dialogs likewise
retain their ordinary lifecycle:
`data-closing` runs the compatible exit state before the owner calls `close()`.

Motion tokens and Fluent easing curves live in `tokens.css`; controls,
expand/collapse, progress, and dialog transitions consume those shared values.
`prefers-reduced-motion` reduces or stops non-essential motion. Virtualized row
creation and recycling never animate, so scroll performance and row geometry
remain stable. GUI Breaks tune choreography without creating another motion
contract.

M1 does not bundle or automatically invoke the Evergreen WebView2 Bootstrapper.
The supported target remains Windows 11; missing WebView2 is refused read-only
with an official installation direction. M1 beta binaries may be unsigned and
must publish hashes, exact source identity, and an honest warning that Windows
or enterprise policy may block unknown unsigned code.

## Adapter boundary

The desktop imports only `NamiSyncService` and its primitive workflow views.
It must not import `core`, `modules`, `db`, CLI internals, or construct a
dispatcher, runtime, workflow request, repository, or recorder.

The service already provides the desktop's command surface:

```python
start_plan(source, target, *, deletion_policy=None, command_id=None,
           observation_sink=None) -> PlanSession
start_execution(request_id, *, verify_after_execute=False) -> ExecutionSession
start_inventory(...), start_baseline(...), start_verify(...), start_rebaseline(...)
read_semantic_settings() -> SemanticSettingsView
commit_semantic_settings(patch) -> SemanticSettingsView
```

`SessionObserver.observe(session_id, sink)` supplies primitive current-state
and event/record views. Plan start's optional sink is attached transactionally
before the session can run. `M1_BRIDGE.md` exclusively defines the recovery
cursor and command-receipt identity exposed across the wire. The desktop owns the bounded
presentation queue fed by that sink; it does not expose raw dispatcher streams to JavaScript. It must
unsubscribe on task close and close every observation before service shutdown.

A loaded-time security, material, or presentation refusal closes dispatcher
admission and wakes the task registry before appearance teardown or any window
close request. Public destruction is attempted once; if that API throws, the
host also checks the closed event and posts one `WM_CLOSE` to its retained
native window handle after either a throw or a return without closure, so the
normal startup-refused path can release the GUI loop. A failure of both close
paths never reopens authority or replaces the original startup diagnosis.

Native load alone does not open a document. The packaged module installs its
appearance receiver and shell DOM, then sends the exact startup-only
`shell_ready` command through the existing sole `dispatch` function. Ordinary
commands remain unavailable until native security/material readiness, that
acknowledgement, and a successful current initial appearance post have all
converged for the current document generation. A fixed five-second product
deadline starts at each native `loaded`;
missing acknowledgement or failed publication enters the same fail-closed
startup-refusal path. The visible `Ready` label waits until the receiver has
actually applied that generation's first valid appearance envelope. A
same-origin reload closes normal admission until the new packaged document
completes the same handshake; stale timers, acknowledgements, and publication
callbacks cannot settle a later generation.

`NamiSyncService.close()` is bounded but not instantaneous: its derived
allowance is twelve seconds, reached only when the audit writer is genuinely
wedged, and a healthy close returns in milliseconds. The host must therefore
never call it from pywebview's `closing` callback, which pywebview runs
synchronously on the WinForms UI thread — a window that stops pumping messages
is marked unresponsive by Windows within a few seconds. The close handler
returns `False` to veto the immediate close, shows a determinate closing
affordance, runs the ordered teardown off the UI thread, and closes the window
programmatically when the `ShutdownView` returns. An incomplete shutdown stays
visible rather than being swallowed by window destruction. The implemented
controller rejects new bridge admission, closes the task registry to wake
drains and capacity-blocked sinks, waits for admitted calls, unsubscribes task
observations, then calls the service. A complete result permits one recursive-safe
programmatic destroy only after window-owned appearance observation closes
exactly once. An incomplete result or exception keeps the window open with
appearance observation still active,
sets fixed retry guidance in the packaged status element, and presents an owned
native Retry/Cancel dialog. Only its Retry choice starts another worker; another
title-bar close can reopen the dialog but neither retries nor force-closes.
Each loaded document binds its current status element before a close worker may
render, so a late worker never queries a destroyed or replaced document;
presentation failure is sanitized and cannot change shutdown truth.
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

The host exposes one function-table `dispatch` entry, and only packaged
`bridge.js` references `window.pywebview`. `M1_BRIDGE.md` exclusively defines
the complete envelope bound, immutable command mapping, opaque identities,
exact errors, deadlines and retry classes, revision rules, drain recovery,
sequence/`Gap`/terminal semantics, and terminal-session release versus explicit
task close. This document requires those mechanisms to produce actionable,
path-sanitized UI feedback; it does not duplicate their wire contract.

NamiSync-owned code never constructs JavaScript or calls `evaluate_js`,
`run_js`, or `Window.state` as an application-data channel. Pinned pywebview
6.2.1 internally constructs JavaScript to return exposed-function results, so
its serializer/escaper and the real-browser hostile-name round trip remain part
of the security boundary. The exact pythonnet 3.1.0 pin is equally part of that
boundary because native delegate subscription, WinForms thread affinity, and
`CoreWebView2` access pass through it. Browserless/Node probes are supplemental;
the installed real-WebView2 witnesses now own the named browser-behavior gates.

The host must force `gui="edgechromium"` and fail with an install action if the
Microsoft Edge WebView2 Runtime is unavailable; silent MSHTML fallback is not
acceptable. Before `create_window` it calls the shared host preparation, which
sets
`OPEN_EXTERNAL_LINKS_IN_BROWSER=False`, `ALLOW_FILE_URLS=False`,
`ALLOW_DOWNLOADS=False`, and `REMOTE_DEBUGGING_PORT=None` and performs only
read-only WebView2 runtime registry access through one side-effect-free
compatibility module. It mirrors pinned pywebview 6.2.1's .NET prerequisite,
accepted Edge channels, and HKCU/HKLM architecture routing, with executable
upstream parity coverage. The `86.0.622.0` token is retained because that
backend passes it to its compatibility helper; NamiSync mirrors the helper's
actual comparison and makes no security-patch freshness claim. A configured
`WEBVIEW2_RUNTIME_PATH` bypasses only Edge-channel discovery, not the shared
.NET/netfx prerequisite read. One typed probe snapshot supplies
both availability and refusal reason: an absent prerequisite names .NET or
WebView2, while an unreadable or malformed registry state reports detection
failure and recommends repair instead of falsely claiming a component is
missing. Host preparation never repeats the .NET registry read merely to choose
its message. The start wrapper repeats
preparation, passes `debug=False`, and uses one zero-argument `initialized`
callback that verifies the selected renderer before invoking the host callback.
Every shipped JavaScript primitive must also run at that admitted floor:
own-property checks use the compatible prototype call, ARIA roles use explicit
attributes, and opaque bridge identities use `crypto.getRandomValues` rather
than newer convenience APIs. Static installed-wheel guards and the real
WebView2 accessibility witness cover that implementation side of compatibility.
Once the static asset server has selected its random loopback port, the host
callback derives the exact origin from the complete `window.real_url` with
`urlsplit` and registers an
idempotent synchronous `before_load` callback. On the WinForms UI thread
`before_load` reaches
`CoreWebView2` and attaches the tested `NavigationStarting`,
`FrameNavigationStarting`, `NewWindowRequested`, and `SourceChanged` handlers
exactly once before application calls are exposed; setup and dispatch workers
never access the UI-affine native object. Top-level navigation outside the
exact packaged asset origin is canceled, every frame navigation is canceled,
and every popup is handled. Attachment failure is sticky and observable:
dispatch remains closed and the host tears down the dead window with an
actionable message after load rather than relying on an exception that
pywebview logs and swallows.

`dispatch` independently rechecks a lock-protected snapshot of the native
committed `CoreWebView2.Source` on every call. It does not authorize from
pywebview's managed `Source` or `get_current_url()`: both can report a rejected
navigation target after WebView2 canceled it and retained the packaged
document. A canceled request leaves the snapshot unchanged, while a genuinely
committed off-origin source replaces it and causes dispatch to fail closed.
Origin authorization is an entry-time admission check; the bridge neither
holds the document lock across a handler nor rolls back completed work if
navigation or reinjection makes its response undeliverable. That state is
uncertain delivery, not uncertain commit; `M1_BRIDGE.md` owns the corresponding
retry and recovery rules. The packaged static-asset server is not an API or
event channel.

The frontend places the restrictive CSP meta element first in `<head>` so no
earlier resource escapes it; `frame-src 'none'` independently blocks frames
during initial parsing before the native hooks exist. DOM APIs such as
`textContent` render all filesystem-derived data. The frontend must never use
`innerHTML`, build executable script from returned data, or interpolate a
filename into an attribute, URL, command, style, or bridge request.
Hostile-name fixtures are required end-to-end.

## Interaction contract

Slice 4 establishes only the presentation core and honest shell frame. It adds
no presentation command or placeholder plan, inventory, history, or control
surface. The page exposes labelled
task navigation and a work region with truthful empty states under the standard
native title frame. `rail.js` and `panels.js` own that accessible frame; they
do not create fake task or session data.

The shared `tree.js` consumes only windows already decided by Python's pure
`visible_sequence.py`. It renders at most 256 returned rows plus fixed virtual
spacers, uses exact 28-CSS-pixel rows and the inert text helper, exposes full
display text to accessibility even when the visual label elides, and ignores a
stale response generation. The root is the single Tab stop, row focus uses
`aria-activedescendant`, and server-derived level, sibling-set, parent, and
first-child metadata support Up/Down/Home/End/Left/Right/Enter navigation even
across a window boundary. `aria-expanded` and the disclosure appear only when
the active filtered projection retains an immediate child: expanded and
collapsed projected parents emit `true` and `false`, while leaves and
structural containers with no retained child emit no expansion state. It never
filters a viewport, reconstructs ancestry,
searches a path, owns selection, or talks to the bridge. Slices 5 and 6 remain the first owners
of real plan/inventory rows and their command wiring. The exact Python
structural/search/filter/window/anchor contract and installed shell/tree
contract live in `M1_BRIDGE.md`; the installed shell/tree witness is SH-G-7 in
`M1_SHELL.md`.

The Slice 4 frame has two labelled structural regions beneath the header: task
navigation stating that no tasks are available and a work region stating that
no task is selected. Landmarks are not gratuitous tab stops; the first real
tree is the operable widget. The completed clean-installed-wheel SH-G-7 run uses
native keyboard events, platform accessibility inspection, native 200% WebView
zoom, and forced-colors emulation against production assets. It verifies focus order and visibility,
usable stacked reflow without horizontal overflow, system-color focus,
hostile and long labels through `render.js`, exact 28-pixel rows, no more than
256 rows plus two spacers, and stale-generation refusal. Python is the sole
validation/window authority and emits the exact renderer view; JavaScript does
not duplicate structural validation. It adds no bridge
command or synthetic domain state. Slice 5 remains the first real plan surface.

The rail itself is a Mica seam: it has no card background, border, or shadow.
An unselected task card is transparent, hover and pointer press use distinct
tokenized overlays, and the selected/current card uses the opaque work-card
selected surface with an accessible neutral boundary and elevation. Forced
colors retain distinct selected hover and press outlines. Selection is
conveyed with `aria-selected`/`aria-current` and is not
inferred from a task's running status. Work panels and tree viewports remain
opaque for readability and scroll performance.

The task rail is a presentation grouping over live service sessions and
retained history, not a new durable task model. It shows activity kind, source
and target when applicable, current phase, progress, and a truthful terminal
headline. Subject-only activities do not fabricate a source-to-target label.
An accepted pause immediately renders **Pausing…** from the existing `pausing`
session state and remains distinct from **Paused** until custody actually
releases. Repeat pause/resume is disabled during that drain, cancellation stays
available, and the next state may be paused or terminal if the active operation
settles the run first.
Successful terminal presentation releases only observation/session authority;
the reviewed plan, task identity, and presentation remain. Task close is a
separate explicit user action, with confirmation/control when work is still
queued or busy. `M1_BRIDGE.md` exclusively defines the exact release and close
commands, ordering, retries, and retained artifacts. Retained history remains,
and the UI never treats a transient progress flag as completion.

Sync remains a two-session interaction: plan first, review its immutable
fingerprint-bound intent, choose a dependency-closed selection, then start
execution with fresh preflight. The service decides whether the selection needs
an explicit destructive confirmation; the browser never derives that risk or
requires a typed phrase. Editing selection or plan-affecting options requires a
new commitment. There is no execute-anyway, auto-commit, or unattended path.
`verify_after_execute` is an explicit option; when selected, the one execution
session may return ordered operation and integrity items plus ordered phase
summaries.

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

The first real plan/inventory search owner uses a fixed 150 ms trailing
debounce. Every search, filter, or collapse intent invalidates earlier response
generations immediately; only the final search in a burst is dispatched, stale
successes and failures are ignored, and the current valid page remains visible
while pending. The pure Slice 4 helper therefore admits the documented bounded
literal query rather than substituting an arbitrary responsiveness limit.

Use accessible text and non-color outcome cues, stable layouts, and full-path
accessibility text for elided paths. Empty, unavailable, ambiguous, blocked,
and failure states must say what the user can do next. The desktop presents as a
Fluent 2 (Windows 11) app that follows the system light/dark theme and reads the
system accent, over a standard window frame on a Mica base; the visual authority
is the design-token/material/motion contract above.
Contrast and no-color-only signaling remain requirements in every theme.

## Acceptance criteria

- A desktop request produces the same facade call, primitive views, result
  classification, and mandatory sync review as the CLI. Console entry points
  remain CLI-only, the GUI entry point retains no console, and an explicit CLI
  subprocess imports no pywebview module.
- The app starts only with Edge Chromium/WebView2, blocks external navigation
  and popups, rejects off-origin dispatch, and transports no application data
  through executable JavaScript text.
- Missing WebView2 is refused before pywebview initialization without writing
  fallback browser settings to HKCU. From the packaged page,
  `window.open('https://example.invalid/')` neither launches the system browser
  nor replaces the document, and the bridge remains usable afterward.
- File logging and the deterministic WebView2 storage path are configured before
  pywebview import. An injected headed-test root receives every local artifact
  and leaves the real per-user directory untouched.
- A bounded coalescing event drain preserves reliable item/terminal ordering,
  makes gaps visible, releases terminal sessions without disposing of their
  reviewed tasks, and closes all remaining observations on explicit close or
  app shutdown.
- Repeated task create/plan-only-close, terminal-close, and busy-cancel-close
  cycles release all process-local task artifacts and keep service, runtime,
  bridge, and adapter maps bounded while retained history remains readable.
- Hostile filenames remain structured data and render as text, never HTML or
  executable content.
- Plan, inventory, settings, and history consume facade views only and remain
  semantically separate; UI cosmetics never change a plan's captured settings.
- Busy, pausing, paused, canceled, refused, partial, degraded, mismatch, and compound
  verification outcomes are truthful and distinguishable without parsing
  strings or inferring status from bytes.
- Tests cover destructive-confirmation gating, location ambiguity, opaque-id authority,
  duplicate/out-of-order bridge responses, event-gap recovery, context target
  selection, process-local restart limits, and one-instance behavior.
