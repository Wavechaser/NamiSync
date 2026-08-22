# M1 Desktop Shell Delivery Plan

Status (2026-08-04, contract realigned 2026-08-14, hardened and reverified
2026-08-17): plan and progress for
the remaining M1 desktop shell. The 2026-08-06 revision folded in the
bounded-history and terminal-cleanup contracts now recorded in `HISTORY.md`
and `DISPATCHER.md` and added sections 5-8; the 2026-08-07 revision settles
single-instance identity,
the database file-pair matrix, in-loop startup teardown, the normative CSP
gate, the GUI argument grammar, and constructor-only command composition; the
2026-08-08 revision added the Fluent visual design language, motion, and the
two GUI Breaks that bound the visual work; their visual authority now lives in
`DESKTOP_UI.md`.
Stages 1-5.5, Phase 0, the WebView2 reality spike, and the existing Slice 1-3
implementation have landed. Their secured host, transport, picker, origin,
privacy, event-drain, and lifecycle contracts are recorded in `M1_BRIDGE.md`;
the installed real-WebView2 browser-behavior migration and fixed, non-sliding
150 ms progress-only linger are complete. The benchmark/accounting checkpoint
has also landed: streamed manifested evidence, post-exit final assembly,
direct-Job child admission, diagnostic-only whole-runtime accounting, and a
path-local retained-state sizer. The frozen/disjoint realistic custody corpora
and production-path runner have also landed. The committed calibration-a
artifact supplies the normative transport measurement, and the separate
contract freezes the 1,966,080-byte ceiling. Three fresh independent holdout-b
runs pass, closing realigned SH-G-8 and BR-G-42 event/transport custody for the
frozen historical v1 representation only. The 2026-08-22 v4 event diagnostic
and Tier-1 current-source custody drift runs passed without recalibrating or
extending that acceptance; `M1_BRIDGE.md` owns their exact disposition.
Other BR-G-42 rows remain on their owning slices. BR-G-45
separately keeps terminal artifact/retention scale open, and
shell-owned SH-G-15 keeps version-bound whole-runtime containment open. GUI
Break 1's token,
component, icon, motion, and native-material
foundation and Slice 4's presentation core/shell frame completed their audited
realignment and were hardened and reverified on 2026-08-17. Slice 5 is the next delivery
slice. NamiSync remains version `0.1.0` until
M1 is complete. Finishing M1 makes the product beta-ready; any later version
change is a separate release decision.

## Standing

`M1_BRIDGE.md` is the sole normative bridge semantics and BR-G acceptance
contract: envelopes, commands, errors, retry/revision identity, sequence and
lifecycle rules live there, not here. `DESKTOP_UI.md` remains the user-facing desktop contract. This file
owns the implementation sequence, frontend/package layout, and release-work
placement for the shell. Its later entry-point and packaging decisions replace
the older statements that bare `nami-sync` opens the desktop or that no GUI
launcher is generated.

The shell does not move domain authority into JavaScript. The desktop remains
an adapter over `NamiSyncService`; the import law, reviewed-plan safety model,
process-local M1 lifetime, and all BR-G gates continue to apply.

### 2026-08-13 audit hardening

The native host uses function-only bridge exposure and fail-closed, retryable
owner teardown. Task/session authority, command policy, and browser recovery
were hardened in the same delivery stream. Their exact behavior and evidence
are normative in `M1_BRIDGE.md`; this plan retains only their host placement and
slice order.

`AppPaths.acquire_lease()` holds non-reparse, delete-denying handles on the app
root, logs directory, WebView2 directory, and both ready database mains for the
headed process lifetime. The database files are bound and the pair contract is
revalidated before commands are exposed. Second-instance activation also
checks that the title-matched HWND belongs to `sys.executable` or the venv's
base interpreter. The fixed named mutex remains deliberately predictable. A
malicious process already running as the same principal can still squat the
mutex or spoof an accepted base interpreter; it is a UX ownership primitive,
not a same-principal security boundary.

Fresh database-pair creation now owns each main and SQLite sidecar through a
Windows reservation lease. Failure cleanup derives a delete handle from the
retained reservation with `ReOpenFile` and requests exact-object disposition,
so a displaced foreign pathname is retained. Rollback runs for ordinary
failures, `KeyboardInterrupt`, and `SystemExit`, and incomplete cleanup carries
the coordinated reset direction.
## 1. Settled Shell Decisions

### 1.1 Entry points

M1 ships one GUI implementation through two correctly classified Windows
entry-point families:

- `nami-sync` is a console script and always routes to the CLI. With no
  subcommand it prints usage, points to `nami-sync-gui`, and exits with the
  existing usage status.
- `python -m namisync` follows the same console behavior through
  `interfaces/launcher.py`; `namisync/__main__.py` no longer imports the CLI
  adapter directly.
- `nami-sync-gui` is a GUI script and starts the desktop without retaining a
  console window.

`interfaces/launcher.py` owns `main(argv=None)` and `gui_main(argv=None)`.
Both adapters are imported lazily: explicit CLI work never imports pywebview,
while GUI logging and path setup complete before the web host imports it. The
import-linter layers become:

```toml
layers = [
    "namisync.interfaces.launcher",
    "namisync.interfaces.cli | namisync.interfaces.web",
    "namisync.interfaces.service",
]
```

This is two launchers for one adapter, not a second GUI implementation.
`[project.scripts]` targets `nami-sync = "namisync.interfaces.launcher:main"`;
`[project.gui-scripts]` targets
`nami-sync-gui = "namisync.interfaces.launcher:gui_main"`.

Because the GUI launcher has no console, `gui_main` owns one minimal native
startup-error reporter: a standard-library `ctypes` call to Win32
`MessageBoxW` with the stable caption `NamiSync - Startup Error`, available
before logging or pywebview import. Expected argument, path, logging,
prerequisite, database-contract, and second-instance activation failures use
that reporter and never rely on stderr. Failures are logged once logging is
available; activation failure remains the already-settled non-error case.

`gui_main` accepts a closed argument grammar: either no arguments, or exactly
one `--data-dir PATH` (the `--data-dir=PATH` equals spelling is accepted). The
GUI-subsystem executable installs no implicit `-h`/`--help` console output.
Unknown flags, positional arguments, a repeated `--data-dir`, a missing value,
and a relative or non-local path are refused before any directory creation,
mutex acquisition, logging configuration, or pywebview import; the native
startup-error reporter shows the reason and the process exits nonzero.

### 1.2 Runtime dependencies

The reality-tested native host stack is part of the product contract:

- CPython 3.13 on Windows 11 x64;
- `pywebview==6.2.1`;
- direct `pythonnet==3.1.0; sys_platform == 'win32'`; and
- direct `bottle>=0.13.4`; version 0.13.4 is the recorded tested
  server version.

Pythonnet 3.1.0 uses .NET Framework through `clr_loader` by default on Windows.
NamiSync supports that tested `netfx` path and refuses a conflicting
`PYTHONNET_RUNTIME` override. The existing read-only .NET Framework probe is
therefore both the pywebview WinForms prerequisite check and the pythonnet
runtime prerequisite check. A dependency change affecting pywebview,
pythonnet, `clr_loader`, or the return transport requires the relevant native
reality and hostile-text gates to be rerun.

### 1.3 Local application paths

One immutable `AppPaths` value resolves the GUI's local artifacts. Production
uses `%LOCALAPPDATA%\NamiSync`; tests and development may inject an isolated
root. Isolation moves every GUI artifact together:

```text
NamiSync/
    ledger.db
    history.db
    settings.json
    ui-state.json
    logs/
        namisync.log
    webview2/
```

A GUI-only `--data-dir PATH` override supplies this application-composition
input for tests and isolated runs. The value must resolve to an absolute local
path, enforced by the §1.1 argument grammar before any side effect; it is never
browser-supplied and never persisted as session authority. A
headed test must pass an isolated root and must not touch the real per-user
directory.

Pywebview starts with `private_mode=True` and an explicit
`storage_path=<root>/webview2`. The pinned WinForms backend chooses the stable
storage branch whenever `storage_path` is supplied. Cookies and remote origin
state are not application authority; the CSP and exact-origin guards remain
unchanged. The predictable directory can be removed by an uninstaller or a
documented web-data reset.

### 1.4 Logging

The GUI configures logging before importing pywebview. The logger is
standard-library-only. It eagerly opens `<root>/logs/namisync.log` in append
mode through `RotatingFileHandler(delay=False, maxBytes=5 * 1024 * 1024,
backupCount=5, encoding="utf-8", errors="backslashreplace")`. Rotation retains
the active file plus `namisync.log.1` through `namisync.log.5`; there is no BOM
or time-based rotation. Eager opening makes an unusable log destination a
startup refusal rather than a delayed surprise, while `backslashreplace` keeps
a malformed surrogate from disabling diagnostics.

The same handler object is attached to the `namisync` and `pywebview` loggers
before pywebview import. Both loggers and the handler use level `INFO`, both
loggers set `propagate=False`, and configuration neither adds a root handler
nor mutates the root logger. This prevents pywebview 6.2.1 from adding its
default console handler and retains swallowed event-handler and native-host
failures without duplicate console or ancestor output. M1 has no log-level
option and does not treat `PYWEBVIEW_LOG` as a product configuration surface.

Every record begins with this stable text header and uses uppercase level names:

```text
YYYY-MM-DDTHH:MM:SS.mmmZ LEVEL pid=<decimal> thread=<thread-name> logger=<name>: <message>
```

The timestamp is UTC with millisecond precision. Exception tracebacks follow
the header as standard formatter continuation lines. This is a human-readable
local diagnostic format, not a versioned interchange schema; individual
message prose is not a compatibility contract.

Immediately after configuration, `startup.begin` records the NamiSync, Python,
and OS versions. `platform.python_version()` and `platform.platform()` supply
the interpreter and OS values. After the lazy imports,
`startup.dependencies` records the installed pywebview, pythonnet, `clr_loader`,
and Bottle distribution versions from `importlib.metadata`; logging
configuration does not import those packages merely to discover metadata. The
registry preflight is availability evidence, not selected-runtime identity.
During native guard attachment on the WinForms UI thread, `startup.renderer`
records the value read from
`CoreWebView2.Environment.BrowserVersionString`; a prerequisite refusal records
its typed reason instead because no renderer exists. Idempotently installed
`sys.excepthook` and
`threading.excepthook` wrappers record an unhandled exception once with its
traceback and then delegate once to the hooks they replaced.

NamiSync-authored diagnostic calls may retain stable event names, opaque ids,
counts, durations, versions, and exception types. They do not format or retain
raw bridge bodies, returned view/domain objects, settings contents, filenames,
or filesystem paths. Tracebacks and OS- or dependency-supplied error text may
incidentally contain Python source or filesystem paths; the local log is
therefore diagnostic data that must be reviewed before sharing, not a promised
path-free artifact. Logging is never the ledger or history audit authority.

Logging configuration is idempotent: repeating it preserves exactly one shared
NamiSync-owned handler and one wrapper per exception hook. Failure to create or
open the application data/log directory is an actionable pre-window startup
failure rather than a silent no-logging mode. A later write failure cannot
change sync, ledger, history, or shutdown truth. Normal exit emits its final
record and calls `logging.shutdown()` after the GUI loop ends.

### 1.5 Product version and license metadata

`namisync/version.py` is dependency-free and contains the single product and
distribution `VERSION` constant. Setuptools reads it through
`[project] dynamic = ["version"]` and
`[tool.setuptools.dynamic] version = {attr = "namisync.version.VERSION"}`.
Runtime/About/logging expose the same value, and a test compares it with
installed distribution metadata. The value stays `0.1.0` throughout M1; this
plan does not preselect the next version or a suffix.

The same module contains the human-facing release nickname `NICKNAME`, set to
`Gertrud` for this release line. It may appear in About, release notes, and a
changelog heading. It is not packaging or compatibility authority: package
metadata, logs, filenames, database markers, mutex names, CLI behavior,
protocol/schema checks, and every version comparison remain tied only to
`VERSION` or to their existing contract-owned versions.

Database schemas, settings, event envelopes, workflow payloads, bridge
messages, semantic policies, contract markers, dependency constraints, and
native-runtime floors keep independent versions beside the contracts that own
them. They are neither stored in nor derived from `version.py`, and changing
one does not mechanically select a product version. A future support view may
aggregate owner-supplied values at the composition root, but it must not copy
them into a second registry. The Python and JavaScript bridge declarations are
the intentional two-language exception and require an agreement test.

The existing GPLv3 `LICENSE` is declared as
`license-files = ["LICENSE"]` in `[project]` during Phase 0. Third-party
notices, corresponding-source release directions, and the frozen
distribution's visible license bundle remain release work after a running
shell exists.

### 1.6 Frontend toolchain and layout

There is no Node.js toolchain, npm, framework, bundler, transpiler, source map,
or inline script. The packaged page loads plain same-origin ES modules:

```html
<script type="module" src="/app.js"></script>
```

Every import names a local `.js` file. The restrictive CSP meta element is the
first element in `head`; no inline script or event attribute is permitted.
Authored assets are the artifacts scanned by the sink gate.

The target layout grows only as its owning slice lands:

```text
namisync/interfaces/web/
    __init__.py
    bridge.py
    document_channel.py
    pywebview_runtime.py
    logging_config.py
    paths.py
    host.py
    appearance.py
    commands.py
    drain.py
    readiness.py
    slots.py
    visible_sequence.py
    assets/
        index.html
        app.css
        tokens.css
        components.css
        icons.js
        icons/
            LICENSE.txt
            SOURCE.json
            checkmark_circle_20_regular.svg
            dismiss_circle_20_regular.svg
            info_20_regular.svg
            warning_20_regular.svg
        app.js
        appearance.js
        bridge.js
        readiness.js
        render.js
        tree.js
        rail.js
        panels.js
        file_row.js
        plan.js
        integrity.js
        inventory.js
        history.js
namisync/interfaces/launcher.py
tests/assets/
    bridge_interactive_probe.mjs
    render_text_probe.mjs
    transport_gate/
```

`visible_sequence.py` owns tree-agnostic flatten/window/search/filter/anchor
presentation. `tree.js` virtualizes and renders windows already decided by the
server; it never reconstructs hierarchy or filters an already-windowed page.
It coalesces passive scroll events and layout-only root resizes through one
animation-frame check and requests a missing spacer index through the
generation it supplies to the owning view. Before root removal, the owner calls
the controller's idempotent disposal to disconnect resize observation, remove
root listeners, invalidate pending work, and suppress an already queued frame.
The dormant `plan.js` and `integrity.js` row primitives reuse only the shared
presentation skeleton in `file_row.js`; the later `inventory.js` renderer stays
disjoint, and `panels.js` owns only their shared panel frame. `tokens.css` holds the Fluent
design tokens defined in `DESKTOP_UI.md`, `components.css` the Fluent control set built on
them, and `app.css` shell/surface layout plus dormant plan-row presentation;
styles and renderers consume token aliases and define no color of their own.

At Slice 2 closure the exact shipped asset set is `index.html`, `app.css`,
`app.js`, `bridge.js`, and `render.js`; later entries in the target layout do
not ship until their owning slices. `render.js` owns the strict production
`textContent` sink; Slice 4's filesystem-label wrapper maps the fixed defended
layout controls to visible markers and delegates to that sole writer. The
browserless probes and headed `transport_gate/` page
remain under `tests/assets/` and are excluded from package data.
GUI Break 1 adds `tokens.css`, `components.css`, `icons.js`, `appearance.js`,
and the exact four SVGs plus source/license records under `assets/icons/`; its
component-gallery scenario remains test-only and absent from the wheel.
The pre-Slice-5 visual checkpoint is the one later-layout exception: packaged
`file_row.js`, `plan.js`, and `integrity.js` expose only dormant presentation
renderers, while `app.js` and `panels.js` remain unchanged and import none of
them. Static projected fixtures under `tests/assets/component_gallery/` call
the installed specializations directly; the fixtures do not ship and
introduce no command, domain object, session, or wire contract. Slice 5 remains
the first owner of real plan/integrity projection, transport, interaction, and
product DOM.
Post-realignment readiness hardening adds `readiness.py`,
`document_channel.py`, and packaged `readiness.js`; it does not add another
bridge or application-data transport.

The production host resolves its index from package resources. A
Python-construction-only override accepts an absolute local index path for
headed tests so the test page and production assets can be assembled under one
temporary root. The production launcher never accepts that override from argv,
the bridge, or page data, and test assets are never package data.

### 1.7 Boundaries owned elsewhere

This plan fixes only implementation and package placement at seams whose
behavioral contract is owned elsewhere:

- `M1_BRIDGE.md` is the sole normative authority for bridge envelopes,
  limits, commands, exact errors, retry/deadline and revision identity,
  visible-sequence behavior, sequence/`Gap`/terminal semantics,
  terminal-session release versus explicit task close, and every BR-G gate.
- `DESKTOP_UI.md` owns the visual and user-facing contract, including the
  exact authored palette, Fluent roles, native materials, icon foundation, and
  motion guardrails.
- `ARCHITECTURE.md` owns layer and lifecycle boundaries; focused module
  documents own domain behavior.

Only `assets/bridge.js` may reference `window.pywebview`; the host exposes
only the function-table `dispatch` entry. Slice 2 places that wrapper and the
strict dispatcher, Slice 3 places the drain manager, and later slices extend
the one transport through rows defined in `M1_BRIDGE.md`. This file neither
duplicates nor refines those protocols.

## 2. Delivery Sequence

### Phase 0 - Before the product shell

Phase 0 contains host-shaping prerequisites and small packaging corrections.
It creates no WebView window.

1. Add the single product/distribution version source and retarget project
   metadata to it; keep `0.1.0`, keep contract/schema versions with their
   owners, and land the installed-metadata agreement test with it.
2. Add GUI `AppPaths` resolution and an injectable isolated data root, with
   path/isolation tests that prove importing it loads no `webview` module.
3. Declare the exact pythonnet dependency and Bottle floor; document and guard
   the tested Windows `netfx` runtime, and pin those declarations with tests.
4. After items 1-3, add bounded file logging and pywebview logger capture, with
   configuration callable before pywebview import. Land exact-header, UTF-8
   fallback, ownership/level, rotation, idempotence, emitted-record,
   exception-hook, safe-startup-record, and no-`webview`-import tests with it.
   Slice 2's real bridge child adds the hostile-body privacy scenario and
   closes SH-G-3; Phase 0 does not pretend dispatch exists yet.
5. Declare `LICENSE` through `license-files` and prove it in built-wheel
   metadata.

Phase 0 does not add frontend assets, entry points, PyInstaller, a lockfile, CI,
third-party notices, signing, or a WebView2 bootstrapper.

### Slice 1 - Product host

1. Rename `security_spike.py` to `bridge.py`; update imports and tests without
   changing the proven security behavior.
2. Add `interfaces/launcher.py`, retarget the console script and package module
   entry point, and add the GUI script described in section 1.1.
3. Extend the layers contract. A subprocess CLI test proves that neither
   `webview` nor a `webview.*` module is present after a real explicit CLI path.
4. Add the initial packaged `index.html`, `app.css`, `app.js`, and `bridge.js`.
   Declare `"namisync.interfaces.web" = ["assets/*"]` under
   `[tool.setuptools.package-data]` and prove a built wheel contains and resolves
   them. The host locates the page with
   `importlib.resources.files("namisync.interfaces.web") / "assets" /
   "index.html"`, so source, wheel, and later frozen execution use one path
   contract.
5. Build `host.py` around the reality-tested startup order:

   ```text
   parse GUI arguments -> resolve AppPaths
   acquire/retain the single-instance mutex or activate-and-exit
   configure logging
   import webview
   prepare_pywebview_host(webview)
   construct NamiSyncService from AppPaths
   validate_database_contracts() -> fresh | ready | refused
       fresh   -> coordinated database initialization
       refused -> native reporter, run finalizer, exit nonzero
   create pending NativeDocumentState
   create startup gate and immutable production command mapping
   compose admit(name) over the final mapping and current readiness context
   create BridgeDispatcher(document=pending_state, commands=mapping,
                           admit=composition_admit)
   create_window(local index path, js_api=None,
                 width=1280, height=800, min_size=(1024, 640))
   expose only dispatch(command_json) through the function table
   start_edge_chromium(http_server=True, private_mode=True,
                       storage_path=paths.webview2)
       initialized -> renderer check
                   -> ExactOrigin.from_url(window.real_url)
                   -> bind pending document origin exactly once
                   -> register synchronous before_load installer
       before_load -> UI thread -> record BrowserVersionString
                                -> attach native guards
       loaded      -> verify attached/no attachment_error
                   -> start fixed five-second readiness deadline
       packaged JS -> install readiness receiver, appearance receiver, shell DOM
                   -> dispatch startup-only shell_ready {}
       host        -> settle safe initial native surface
                   -> post current-generation neutral challenge
       packaged JS -> dispatch readiness_echo {challenge}
                   -> open ordinary commands only after post/echo converge
   ```

   Dispatch remains closed while document authority is pending or failed.
   Width, height, and minimum size are logical pywebview construction values;
   its WinForms backend owns DPI conversion. Private window fields are not
   mutated to solve construction order or geometry. The former viewport media
   query is removed; a 48 rem inline-size container preserves stacked reflow
   under WebView2 zoom despite the native minimum.

   A failure before `start_edge_chromium` unwinds acquired state through one
   bounded finalizer: close the service if constructed, log any cleanup failure
   without replacing the original startup failure, shut logging down if
   configured, release the mutex, show the failure through the native reporter,
   and exit nonzero. The losing second instance never configures the rotating
   logger, so two GUI processes cannot rotate the same file.

   Two failures happen *inside* `start_edge_chromium` and are routed toward
   that same finalizer, because pywebview swallows event-handler exceptions and its
   decorated close can wait ~20 seconds for a window that was never shown:

   - **Initialized failure** (renderer or origin, which pywebview invokes
     *before* it creates the native window): record the renderer/origin
     failure, return `False` to abort creation, let `start_edge_chromium`
     return, and do **not** call `window.destroy()` — no native window exists.
   - **Initial guard or pre-open loaded failure** (native attachment on the UI
     thread): store the sticky failure, synchronously reject bridge admission
     and wake the task registry, mark the host startup-refused, and call
     `window.destroy()` exactly once. If that public call throws or returns
     without setting the closed event, post one `WM_CLOSE` through the retained
     HWND. The `loaded` watchdog stores state and closes rather than raising;
     both close paths leave authority rejected if they fail. The finalizer
     cannot run until a successful request or later manual/native closure lets
     the GUI loop return.

   Native `loaded` is necessary but not sufficient for an open document. The
   packaged module must acknowledge receiver/DOM installation through the sole
   dispatch entry, and the initial native surface must settle safe. The host
   then posts a neutral current-generation challenge through the sole document
   channel, and that page echoes it through `readiness_echo`. Missing
   acknowledgement, unsafe surface settlement, or a failed or incomplete
   post/echo before the five-second deadline and before the first open
   generation enters the same terminal startup-refused path; close and late
   callbacks cannot reopen it. Appearance configuration, observation, read, or
   publication failure degrades over a confirmed opaque base and is not itself
   a readiness refusal; only an unconfirmed opaque rollback after native
   surface mutation is unsafe. The visible `Ready` label waits for the truthful
   echo acknowledgement. A same-origin reload closes ordinary admission before
   reinjection and must repeat the bilateral handshake; stale timers,
   acknowledgements, and queued posts cannot settle its new generation. If that
   reload handshake refuses after an earlier generation opened and the host
   remains open, it records the failure and uses the ordinary bounded
   service-close path rather than bypassing active work with the startup-only
   destroy. A close already in flight retains ownership and a later readiness
   refusal cannot replace it. Raw pywebview API injection is sufficient only
   for the bootstrap rows `shell_ready` and `readiness_echo`; normal calls,
   retries, and retained task drains stay paused until the echo is acknowledged.

   After `start_edge_chromium` returns, both initial in-loop refusal paths run
   the finalizer above. If both close requests fail, authority remains rejected
   until later manual/native closure makes that return possible. Because
   ordinary dispatch never opened on this initial path, `service.close()`
   should return a complete shutdown view; an incomplete result or exception is logged, but
   there is no Retry Close affordance and startup still terminates nonzero.
   Tests cover both the pre-native initialized failure and the post-native
   guard-attachment failure.
6. Implement the host close state machine now: user close is vetoed on the UI
   thread, closing becomes visible, one teardown attempt starts off-thread, and
   the later programmatic close is allowed through without recursively starting
   teardown.
   The eventual teardown order is reject new dispatches, wake drains and
   capacity waiters, wait for admitted handlers, unsubscribe task observations,
   call `NamiSyncService.close(timeout)`, and destroy only when the returned
   shutdown view is complete. The service call retains its existing internal
   order: `SessionObserver.close()` closes streams and joins observers before
   dispatcher/runtime closure. The host does not reach into the service to
   close that observer twice. At most one teardown attempt runs at a time. An
   incomplete result or teardown exception leaves the window open with the
   unfinished state and a Retry Close action; retry starts another off-thread
   attempt, and there is no force-destroy path. The initial, pre-open startup-
   refused phase from step 5 is the one exception: its closing handler
   recognizes that phase and bypasses this veto/Retry machine entirely. Its
   single public-destroy/native-close request asks the GUI loop to return; the
   bounded finalizer follows only after it does. If both requests fail,
   authority remains rejected until later manual/native closure. A readiness
   refusal after an earlier open generation uses this ordinary teardown machine
   instead. Slice 1
   supplies empty wake/subscription hooks for later slices rather than blocking
   the UI thread.
7. Add a per-logon-session single instance built on one injected
   `DesktopInstanceIdentity(mutex_name, window_title)`. The production launcher
   always constructs the fixed, version-independent pair
   `DesktopInstanceIdentity(mutex_name=r"Local\NamiSync.Desktop",
   window_title="NamiSync")`. The `Local\` namespace is deliberate — one
   instance per Windows logon session, not one across all users: a `Global\`
   mutex would make separately signed-in users fight over one instance, and
   cross-session activation could not work anyway. The name carries no product
   version, `AppPaths`, or `--data-dir` component; a version component would let
   an old and a new install run at once, and a data-root component would be an
   undocumented multi-instance switch.

   Both sides consume the same immutable object rather than re-deriving a
   string, so there is nothing to keep in agreement (both consumers are Python;
   unlike `ROW_H`, this needs no cross-language parse test). The first instance
   holds `identity.mutex_name` for the host lifetime and passes
   `identity.window_title` to `create_window`; a losing launch probes that same
   mutex, calls `FindWindowW` with that same title, restores the window,
   attempts `SetForegroundWindow`, reports activation failure visibly, and exits
   zero. No IPC or `AllowSetForegroundWindow` protocol is introduced. The
   production title stays fixed for the window lifetime — task name and status
   live inside the page, because retitling the window would break activation
   discovery.

   The mutex is authoritative; the title is only a discovery mechanism. A second
   launch can lose the mutex while the first instance is still creating its
   window, and the existing "activation failure is visible and non-error" rule
   already covers that startup race without adding IPC.

   Tests receive an injected identity through Python construction only —
   `test_instance_identity(unique_token)` deriving a private pair such as
   `Local\NamiSync.Test.<token>` / `NamiSync Test <token>` — so concurrent
   headed hosts get independent mutexes and can never find or activate a real
   user window. The instance namespace is never selectable through argv,
   environment, bridge command, or page content: the production launcher always
   supplies the fixed production identity, and only the headed harness supplies
   a test identity, directly at host construction.
8. Give database state a coordinated preflight with a visible refusal surface.
   Add the service facade's read-only `validate_database_contracts()` preflight
   and call it before window creation and before any command admission. It
   reads the existing ledger/history main files, their role-specific version
   and contract markers (ledger and history carry intentionally different
   marker values), and their WAL/SHM/journal sidecars, and returns a pair state
   — `fresh`, `ready`, or `refused` — without mutating anything:

   | State | Result |
   | --- | --- |
   | Both main files and all sidecars absent | `fresh`: coordinated initialization before window creation or command admission |
   | Both main present, each matching its own expected version and contract marker | `ready` |
   | Both present, but either is empty, unversioned, outdated, or wrong-marker | `refused`: read-only coordinated-reset direction |
   | Exactly one main file present | `refused`: typed inconsistent-pair; the missing peer is not created |
   | A main file absent but its WAL/SHM/journal sidecar present | `refused`: inconsistent-pair, not fresh initialization |

   Fresh initialization is a **separate** operation from the read-only
   preflight, so validation itself never writes. A caught partial
   fresh-initialization failure removes only the artifacts that attempt created
   and never deletes a pre-existing file; a crash between the two publications
   is recovered by the exactly-one-present refusal on the next launch. On
   `refused`, the launcher's native startup-error reporter shows the documented
   coordinated manual reset direction, the GUI never exits silently, migrates,
   or deletes, and every existing database file is byte-identical afterward.

   This is a service-facade contract, not a GUI-only guard. Every composition
   that can mutate both databases — the GUI and the CLI
   sync/inventory/integrity paths — runs the preflight and coordinated
   initialization, closing the existing hole where audit observation could
   initialize history before execution recording initializes the ledger. A
   deliberately standalone read-only history command may remain exempt. The
   matrix proves a consistent present pair, not common provenance; proving two
   files came from one installation would need a shared pair UUID and schema
   bump, which is out of scope for M1.

Slice 1 closes the revised BR-G-19 and BR-G-31 host clauses. It proves wheel
installation, not yet the final PyInstaller artifact.

### Slice 2 - Command transport, slots, and headed harness

Status: implementation and installed real-WebView2 browser evidence complete.

The normative transport contract is exclusively in `M1_BRIDGE.md`: its
inherited bridge posture, DR-BR-25/27 decisions, Slice 2 delivery contract, and
BR-G-32 acceptance gate own envelopes, limits, command schemas, error
vocabulary, retry identity, deadlines, and command-specific revision rules.
This shell plan owns only when and where that contract lands.

Delivery work:

1. Add `commands.py` for immutable constructor-supplied command composition
   and `slots.py` for server-held native-picker authority.
2. Complete `bridge.py` as the strict dispatch/codec/refusal boundary and keep
   `assets/bridge.js` as the sole browser transport owner.
3. Compose the production rows, native picker, committed-origin check, and
   sanitized logging through the Slice 1 host without moving domain policy into
   the adapter.
4. Add ordinary boundary tests and a constructor-only installed-wheel headed
   harness under `tests/`; test commands and pages remain absent from package
   data.

This slice maps SH-G-3 to the transport/privacy portion of BR-G-32. The Python
boundary, picker confinement, origin refusal, and hostile-text path are
implemented. The named gate now runs those wrapper cases through the real
installed WebView2 composition; Node probes for those wrapper cases remain
supplemental evidence. The later Slice 3 drain-manager Progress
validator/replay probe is the sole ordinary non-skippable Node gate.

### Slice 3 - Event drain

Status: the existing implementation, realigned 150 ms progress-only linger,
frozen custody corpora, production-path runner, and normative calibration-a
artifact plus frozen 1,966,080-byte ceiling have landed. Independent holdout-b
passes, so the frozen historical v1 SH-G-8 and BR-G-42 event
correctness/transport-custody claim is closed; current-version latency
acceptance remains on its separate BR-G-42 rows.

The exact event command, queue policy, recovery cursor, explicit-`Gap`
semantics, terminal reconciliation, retry behavior, and terminal-session
release versus explicit task close are normative only in `M1_BRIDGE.md`
(DR-BR-21/22/24 and BR-G-33/41/42). This plan records their delivery placement:

1. Add `drain.py` for adapter-owned task identity, observation generations,
   bounded event custody, long-poll claims, recovery, and lifecycle cleanup.
2. Extend the constructor-supplied command mapping and `bridge.js` drain
   manager in the same atom; no later surface command lands early.
3. Attach observation transactionally before scheduling through the existing
   service/dispatcher seam, and preserve shutdown ordering through the Slice 1
   close controller.
4. Add ordinary concurrency/overflow/recovery tests and extend the installed
   headed harness; keep transport probes test-owned.

The explicit-`Gap`-only recovery decision and the command-specific
`start_plan` revision decision are ratified in `M1_BRIDGE.md` and now have
named regressions. Numeric sequence holes alone are not a recovery signal, and
session creation does not invent a revision.

SH-G-8 acceptance evidence and its residual scale boundaries are consolidated
under the gate in §5. `M1_BRIDGE.md` BR-G-42 remains the sole authority for the
event contract, custody roots, corpus, measurement method, and bridge timing
rows.

### GUI Break 1 - Presentation foundation (completed 2026-08-13; hardened and reverified 2026-08-17)

GUI Break 1 sits after Slice 3 and before Slice 4. It placed `tokens.css`,
`components.css`, `icons.js`, `appearance.js`, and the fixed local icon
assets in the package, with a test-only component gallery outside package
data. The exact visual contract lives in `DESKTOP_UI.md`; SH-G-11 through
SH-G-14 below map its installed/headed evidence to the BR-G dependencies in
`M1_BRIDGE.md`.

### Slice 4 - Presentation core and shell frame (completed 2026-08-13; hardened and reverified 2026-08-17)

Slice 4 placed `visible_sequence.py`, `tree.js`, `rail.js`, and
`panels.js`, then connected the honest empty shell frame. It introduced no
second transport. The pure presentation and BR-G-34 contracts live only in
`M1_BRIDGE.md`; SH-G-7 records the installed shell/tree witness. GUI Break 1
must be complete before the production renderer consumes its tokens and
components.

### Slice 5 - Sync surface

Land the plan projection and review surface, selection controls,
destructive-confirmation flow, execution admission, progress identity, and
indexed follow mode. Extend the existing transport only through the Slice 5
command rows and gates defined by `M1_BRIDGE.md`. Close BR-G-35 through
BR-G-37 and the plan portion of BR-G-42. The validated Python projection may
map into the dormant page-local row view, but that object is not a frozen wire
payload and creates no backwards-compatibility obligation for the bridge.

### Slice 6 - Inventory and integrity surface

Land cached inventory projections, location-resolution presentation,
recursive folder actions, scope warnings, integrity controls, and bounded
detail queries. Extend the existing transport only through the Slice 6 rows
and gates defined by `M1_BRIDGE.md`. Close BR-G-22, BR-G-23, BR-G-38,
BR-G-39, and the inventory portion of BR-G-42.

### Slice 7 - Lifecycle, settings, and history

Land database-paged history, semantic settings, the remaining typed
`ui-state.json` consumers, and the task-owned cleanup UI on the cosmetic
channel frozen by the pre-Slice-5 checkpoint. The exact lifecycle and history
bridge rows remain exclusively in `M1_BRIDGE.md`. Design and prove BR-G-45's complete
100,000-subject terminal artifact set and aggregate completed-task retention
policy, then close BR-G-40, BR-G-41, BR-G-45, and the history portion of
BR-G-42.

### GUI Break 2 - Visual cohesion

After the real plan, inventory, history, and settings surfaces coexist, perform
the holistic spacing, motion, empty/error-state, accessibility, and responsive
review defined by `DESKTOP_UI.md`. It precedes Slice 8.

### Slice 8 - Beta packaging and release closure

Add the frozen specification, dependency lock and CI, third-party notices,
source-release material, frozen smoke, and clean-checkout release proof.
Enforce and headed-test the `DEFENSE.md` standard-integrity host requirement
before any command is exposed; an elevated launch refuses actionably unless the
defense model is first revised. Treat exact dependency pins as behavioral
authority and separately document the supported security-update posture.
Reconcile active documentation and the `ui_mockup/` reference against the
as-built product. Close BR-G-43, BR-G-44, and the version-bound SH-G-15
whole-runtime containment gate.

## 3. Test Commands

Register a `headed` pytest marker and make `-m "not headed"` the configured
default. The headed and release commands clear that default explicitly; the
release command then collects every BR-G and SH-G gate:

```powershell
# Ordinary development suite
.\.venv\Scripts\python.exe -m pytest -q

# Real WebView2 scenarios
.\.venv\Scripts\python.exe -m pytest -q -o "addopts=" -m headed tests\interfaces\web

# Release evidence: list, then run, headed and ordinary tests
.\.venv\Scripts\python.exe -m pytest --collect-only -q -o "addopts="
.\.venv\Scripts\python.exe -m pytest -q -o "addopts="
.\.venv\Scripts\lint-imports.exe
git diff --check
```

On the supported Windows profile, missing WebView2 fails headed verification
actionably; it is not a skip or xfail. Every `test_br_g_*` and `test_sh_g_*`
test is collected by the release command.

## 4. Explicit Deferrals

The following do not block the first running shell but do block or qualify the
first beta release as stated above:

- PyInstaller/frozen artifact work: Slice 8.
- CI and dependency lock: Slice 8.
- Third-party notices and GPL source-release directions: Slice 8.
- Paid code signing or Store publication: post-M1; unsigned-beta limitation is
  documented.
- Evergreen Bootstrapper bundling and Windows 10 support: post-M1 decision.

Durable sessions/plans, cross-process task visibility, retention, general
schema migration, unattended execution, and a remote API remain outside M1 as
specified by the existing milestone documents.

## 5. Shell Acceptance Gates

`M1_BRIDGE.md`'s BR-G contract remains the primary acceptance authority; the
slice-to-gate mapping in section 2 is unchanged. The SH-G gates below pin only
decisions this file owns. Each is written so that the least-effort
implementation that satisfies it is still a correct shell: every gate names an
observable behavior, a counterexample or fault injection, and the shortcut
that does not count. Headless SH-G tests join the ordinary suite; headed ones
carry the `headed` marker; all are collected by the release command.

- **SH-G-1 — Entry points are classified by the operating system, not by
  intent.** From a built wheel installed into a clean venv: `nami-sync` with
  no subcommand prints usage naming `nami-sync-gui` and exits with the
  existing usage status; a subprocess probe proves no `webview` or `webview.*`
  module is loaded after a real explicit CLI command; `python -m namisync`
  behaves identically; and the generated `nami-sync-gui` executable's PE
  header declares the Windows GUI subsystem. *Not satisfied by* calling
  launcher functions in-process, patching `sys.modules`, or asserting on a
  source checkout where console scripts were never generated.
- **SH-G-2 — One root owns every GUI artifact.** With an injected isolated
  root, the ledger, history, settings, ui-state, log, and `webview2`
  artifacts all resolve beneath it; a headed `--data-dir` run leaves the real
  per-user directory untouched, proven by an identical before/after snapshot
  of that directory rather than by trust; a relative `--data-dir` is refused
  before it creates any directory. A static scan of
  `namisync/interfaces/web/` plus
  `namisync/interfaces/launcher.py` proves only `paths.py` reads `LOCALAPPDATA`
  or uses `NamiSync` as a path component. The existing workflow default
  resolver remains the independent CLI authority. *Not satisfied by*
  unit-testing the GUI resolver while another GUI component builds its own
  path.
- **SH-G-3 — Logging is proven by emitted records.** Configuring twice yields
  one shared handler, one wrapper per exception hook, no root mutation, and the
  exact levels and propagation policy from section 1.4. An ordinary successful
  child GUI-path process eagerly creates `namisync.log`, emits a parseable UTC
  header with the required fields, captures pywebview records in the file, and
  writes nothing to the console. Its startup records contain the specified
  product/interpreter/OS and installed dependency versions; the headed scenario
  records the selected renderer's native `BrowserVersionString`, not a registry
  guess. ASCII fixtures cross the configured 5 MiB rollover threshold and
  create the numbered backup; separately, valid non-ASCII text remains UTF-8
  and a malformed surrogate is backslash-escaped without an internal logging
  failure. Separate injected
  thread-level and process-level exception scenarios each log once and delegate
  once. A dispatched hostile command containing a unique synthetic path
  sentinel leaves neither its raw body nor that sentinel in the emitted file.
  *Not satisfied by* asserting handler configuration without records or by
  logging only from the test process.
- **SH-G-4 — One product version, three witnesses.**
  `namisync.version.VERSION`,
  installed distribution metadata, and the startup log record agree, with the
  metadata read from the installed distribution. Importing
  `namisync.version` in a fresh subprocess loads no other NamiSync submodule.
  *Not satisfied by* comparing the constant to itself, importing an owning
  layer through `version.py`, or treating a schema/protocol version as a fourth
  witness.
- **SH-G-5 — Database contract refusal has a visible GUI surface.**
  Fault-injecting mismatched ledger/history contract markers into an isolated
  root produces the documented coordinated-manual-reset direction on a
  visible GUI surface, leaves every database file byte-identical, and does
  not exit silently. A parent process with a hard timeout finds the production
  Win32 dialog by its stable caption, reads its child control text, dismisses
  it, and asserts the child exit. This Slice 1 check needs neither the later
  WebView harness nor a new dependency. *Not satisfied by* a log-only refusal,
  a mocked reporter, or testing the service exception without the GUI surface.
- **SH-G-6 — The wheel is the artifact under test.** The built wheel contains
  every packaged asset, `importlib.resources` resolves `index.html` from the
  installed wheel in a clean venv, and the headed smoke scenario loads that
  resolved page. *Not satisfied by* resolving from the source tree.
- **SH-G-7 — Static frontend invariants scan the shipped file set.** Over the
  exact asset set the wheel ships: `window.pywebview` appears only in
  `bridge.js`; `index.html` carries exactly one Content-Security-Policy `<meta>`
  element, the first element of `head`, whose raw ASCII content value equals
  `M1_BRIDGE.md`'s normative policy string byte-for-byte (the expected literal
  lives in the test); no inline script or event attribute exists; and the
  CSS/JS row-height declarations are integer-equal, with the headed hostile-row
  measurement matching `ROW_H`. The clean-installed-wheel Slice 4 scenario also
  proves the real empty shell exposes labelled task navigation and a work
  region without fake data, preserves keyboard focus and usable reflow at 200%
  zoom, retains visible system-color focus cues under forced colors, and reads
  the operable hierarchy from Chromium's platform accessibility tree. The
  same scenario imports the installed `tree.js`, keeps a natively moved active
  descendant fully visible in a one-row viewport, uses CDP pointer hit testing
  to prove disclosure toggle without activation and ordinary label activation,
  grows a settled two-row viewport to four without scrolling, requests and
  covers the newly exposed index, sends a native CDP mouse-wheel gesture
  through that four-row viewport, accepts the requested five-row page without
  changing scroll position, and proves the
  visible region stays nonblank with a fully visible active descendant and no
  domain activation, then disposes the controller before root removal and
  proves queued or later resize/scroll work admits no request,
  renders every defended layout character and input marker delimiter as its
  exact injective `⟦U+XXXX⟧` marker with no surviving active layout control in
  either the DOM or Chromium accessibility name, preserves ordinary markup-
  like text, Arabic, Hebrew, combining sequences, emoji/variation selectors,
  ZWNJ/ZWJ, and long strings exactly, and returns raw opaque node ids through
  toggle/activation callbacks. It measures every row at
  28 CSS pixels, proves the DOM never exceeds 256 data rows plus fixed spacers,
  and proves a stale generation cannot replace a newer window. The matching
  Python/wire and production-module regressions use one canonical temporary
  JSON manifest generated through the production workflow-tree,
  visible-sequence, window, and wire-view chain. Direct Node and the installed
  WebView2 child consume those exact bytes; Python, child, and page SHA-256
  values match. The cases cover the `head`, `next`, `tail`, `empty`, `maximum`,
  and `layout_control` views, expansion tri-state across the pointer and
  projected-empty views, and ordinary-Unicode and long-label values in `next`.
  The exhaustive fixed-set sink case remains renderer-local
  because C0 characters are not valid Windows filename input; it proves the final
  transform without fabricating workflow provenance. The manifest and helper
  remain test-only and absent from package data. *Not satisfied
  by* scanning a hand-maintained file list, asserting only the meta element's
  presence, testing the component gallery instead of the production shell, or
  measuring a copied/test-only tree implementation or independently authored
  positive renderer rows.
- **SH-G-8 — CLOSED FOR THE FROZEN V1 REPRESENTATION (2026-08-14):
  attach-before-start event delivery and transport custody are bounded.** The
  ordinary four-task fixture covers 60
  logical seconds, 6,000 `Progress` emissions, 600 reliable items, and four
  terminal records. It proves attach before tick zero, ordered exactly-once
  reliable delivery, monotonic coalesced progress, terminal truth, no normal
  `Gap`, and subscriber/adapter queues no larger than 64. A separate
  260-reliable beyond-envelope case proves visible `Gap`, retained-tail
  recovery, and terminal reconciliation without claiming lost events returned.

  Progress-only drains use one non-sliding 150 ms deadline from first
  availability. The first detailed progress on an idle task may wait that full
  interval; receipt and reliable running-state feedback bypass it, as do
  `Gap`, terminal, close, supersession, and recovery values.

  Custody acceptance follows `M1_BRIDGE.md` BR-G-42 and counts the
  identity-deduplicated replay, subscriber, and adapter graph while excluding
  terminal-result subtrees. The real production queue path reaches the exact
  per-task 128/64/64 no-`Gap` shape and ordered cleanup under frozen, disjoint
  realistic corpora. Calibration-a measured 1,376,690 ordinary and 1,534,946
  exact-maximum bytes; a later contract froze the independently derived
  1,966,080-byte ceiling. Three fresh holdout-b runs passed at 1,351,794 and
  1,513,014 bytes under the frozen real-Git validator. A one-child current-
  source regression guards both live shapes against the same ceiling without
  becoming new acceptance evidence.

  On 2026-08-22 the v4 installed-wheel event diagnostic and the protected
  one-child plus three-child current-source custody characterization also
  passed. They are respectively diagnostic and Tier-1 drift evidence: neither
  creates current-v4 Tier-2 timing acceptance nor recalibrates the v1
  authority. `M1_BRIDGE.md` records their fixture, receipts, values, and exact
  disposition.

  This closes the frozen v1 SH-G-8 and BR-G-42 event
  correctness/transport-custody claim only.
  Current-source latency acceptance remains open on its BR-G-42 row; terminal
  result retention belongs to BR-G-45, and complete headed-runtime containment
  belongs to SH-G-15. The earlier 67,375,104-byte whole-Job result is diagnostic
  only. *Not satisfied by* attaching after start, sliding the progress deadline,
  delaying reliable values, hiding loss behind terminal recovery, measuring
  payload or whole-process bytes as transport custody, charging terminal
  artifacts to custody, or letting calibration validate its own limit.
- **SH-G-9 — The history pager terminates on the empty terminal page.** A
  fault-injected traversal whose live cursor is ahead of durability renders
  the committed prefix and stops on the empty terminal page; a later repair
  captures the new committed prefix through a fresh read that omits
  `through_seq`; a request counter proves no retry loop. *Not satisfied by*
  treating the empty terminal page as an error or by testing only a fully
  durable run.
- **SH-G-10 — Single-instance identity is one fixed contract, injected for
  tests.** The production launcher always constructs the fixed
  `DesktopInstanceIdentity` (`Local\NamiSync.Desktop`, title `NamiSync`), and
  changing `AppPaths` or `--data-dir` leaves both values unchanged. Two launches
  on the production identity collide on the mutex; two headed hosts built with
  distinct injected test identities coexist. The title passed to `create_window`
  and the title the activator passes to `FindWindowW` both come from the one
  injected object, and a test identity never searches for or activates the
  production title. No production entry point — argv, environment, bridge, or
  page — exposes an instance-namespace override. *Not satisfied by* asserting a
  constant equals itself, deriving identity from the data root, or a test that
  shares the production namespace.
- **SH-G-11 — Tokens own color; surfaces borrow it.** `tokens.css` defines the
  color/type/spacing/radius/elevation variables in light, dark, and
  high-contrast. The implemented color-semantic checkpoint contains exactly the
  15 authored `--palette-*-main|dark|light` primitives from `DESKTOP_UI.md`.
  Yellow main is `#FFAA22`, purple main is `#8844CC`, and their former main
  values are the new yellow light `#FFDD44` and purple light `#BB88EE`;
  operation consumers remain bound to main. Hued semantic badges explicitly
  use light/dark family surfaces with contrast-safe labels: Light red/yellow
  fills use their dark tones, Dark fills use main labels, while Dark relocating text
  uses purple-light. Channel-specific aliases keep plan
  intent, task lifecycle, and integrity distinct. Hue identifies class, form
  expresses attention, and text plus non-color cues preserve meaning.

  Headed gallery evidence covers every ratified case in its owning form. Intent
  covers `copy`, `mkdir`, `move`, `recase`, `update`, `move_update`, `trash`,
  `delete`, `noop`, `error`, `unsupported`, and `blocked`. Lifecycle covers
  neutral new/planned/queued; accent execution, verification, pausing, and
  canceling; green completion; yellow partial/degraded/incomplete and paused or
  recoverable interruption; neutral-filled plain cancellation; yellow-filled
  refused and post-mutation cancellation; and red-filled failure.
  Integrity covers `VERIFIED`, `BASELINED`, `UNVERIFIED`, `MODIFIED`,
  `REAPPEARED`, `UNSUPPORTED`, `CANCELED`, `MISSING`, `MISMATCHED`, and `ERROR`,
  including reappearance precedence over ordinary unverified/modified display.
  The plan and integrity renderers wrap supplied labels, accept only the exact
  already-projected keys for those two channels, and carry no form field or
  JavaScript domain inference. Narrow optional lifecycle keys render test-only
  Copying/Verifying full-cell 4 px progress specimens from an explicit projected
  0–100 percentage and Completed text specimens. Supplied active text remains
  accessible; JavaScript derives neither a transport ratio nor row identity.
  Text forms have no semantic background; filled forms are borderless 18
  logical px badges with family-light/dark-label pairs in Light and
  family-dark/main-label pairs in Dark. Compact row badges share the checkbox's
  4 px radius and align their text with unfilled labels. Active operation chips
  use exact family main at rest and the same RGB at 90%/80% strength for hover
  and press, without lift or scale. Paused
  progress freezes yellow, plain canceled progress freezes neutral gray, and
  resume restores accent. The stopped-count/percentage enhancement remains
  latent and adds no present payload field. Unchecked checkbox evidence uses a
  1 logical px neutral boundary; textbox underlines and dual focus strokes keep
  their existing dimensions.

  Computed light/dark checks require at least 4.5:1 for normal text and 3:1 for
  large text, non-text indicators, and focus/control boundaries except for the
  explicit main-color text cases recorded in `DESKTOP_UI.md`; all filled badge
  pairs meet the ordinary normal-text contrast floor. Those text cases retain
  the full visible state word, record the measured ratio rather than claiming
  conformance, and become system colors in forced colors. Forced-colors evidence
  proves those aliases use system colors instead of the authored palette. A
  static ownership scan proves raw color literals and
  direct `--palette-*` consumption occur only in `tokens.css`: neither
  `components.css` nor any Slice 4-7 stylesheet/renderer may contain raw colors
  or consume a palette primitive directly. *Not satisfied by* a single-theme
  token set, treating a `light` primitive as an automatic light-theme foreground,
  color- or form-only status meaning, applying one generic status alias across
  conflicting channels, rerouting operation consumers to contextual tones,
  allowing JavaScript to infer domain semantics, or
  a scan that allows inline color in `components.css` or a surface module.
  The neutral/type/spacing/radius/motion/elevation subset is transcribed from
  pinned `@fluentui/tokens@1.0.0-alpha.24` source at commit
  `32b42a5bf79c1836047dfc7fae07b1320731bce4`; exact source-file hashes and
  values are retained as test fixtures. Accessible Fluent stroke roles, not
  decorative subtle strokes, own control and focus boundaries. The headed
  gallery resolves production `index.html`, `tokens.css`, and
  `components.css` from a clean installed wheel and records their exact bytes;
  a source-tree stylesheet or copied/reimplemented component sheet is not
  release evidence. The gallery page itself remains tests-only and absent from
  the wheel. The installed token, component, renderer, and gallery
  implementation supplies this revised foundation without activating dormant
  production task or file-list surfaces.
- **SH-G-12 — Native materials apply or degrade, never break.** On a capable
  system the DWM Mica backdrop and immersive dark title bar are applied and the
  WebView2 background is transparent; Mica shows through the intended seams —
  title bar, rail, and card gutters — while background/content cards composite
  the tokenized low-opacity primary material blend over that base; under high
  contrast Mica is disabled, those cards become opaque system surfaces, and
  the high-contrast palette is honored. The clean-wheel composition witness
  injects the native
  high-contrast snapshot and activates renderer `forced-colors` in the same
  real WebView2 window, asserts dynamic system-color resolution, and retains
  every native Mica-off check; it is not evidence of a real OS theme toggle.
  On a pre-material system or an injected transparency failure the
  window falls back to a theme-correct opaque Fluent neutral base. A fallback
  is claimed only from structured backdrop/glass/form/controller landing
  evidence sufficient to prove that the client is readable. If a later live
  reapply confirms neither native path, the receiver publishes `degraded` and
  returns the page base itself to the theme-correct opaque neutral rather than
  preserving a stale Mica claim. Live UISettings changes publish the exact
  accent rest/hover/pressed and contrasting foreground roles through the fixed
  revisioned appearance receiver. Observation subscribes before its mandatory
  first read and coalesces native notifications into bounded UI-thread turns;
  only a current-state read receives the latest revision, and close invalidates
  queued turns. Native load, packaged `shell_ready` acknowledgement, safe base
  surface settlement, and a neutral current-generation host challenge/page
  echo must converge within the fixed five-second loaded-time deadline before
  ordinary bridge commands open. The nonce proves liveness rather than
  authority and is neither logged nor persisted. Appearance publication is
  independently degradable after surface safety settles; the page reports
  `Ready` only after the readiness echo is acknowledged. Reload closes ordinary
  admission until the new generation repeats the bilateral handshake.
  Material application changes neither the security guards nor the construction
  order. *Not satisfied by* a documentation lookup, a mock window, or a test that
  never exercises the fallback.
- **SH-G-13 — Motion honors the guardrails.** With `prefers-reduced-motion` set,
  non-essential transitions reduce or stop; a static/DOM check proves no
  animation or transition is bound to virtualized-row creation or removal in the
  plan or inventory tree. A dialog remains open while its compatible
  `data-closing` exit transition runs, then closes through the ordinary dialog
  lifecycle. *Not satisfied by* asserting the media query exists
  without a reduced-motion render, or by checking only a non-virtualized list.

- **SH-G-14 — Icons are local, closed, and token-colored.** The installed wheel
  contains the exact four pinned Fluent regular SVGs from
  `@fluentui/svg-icons@1.1.334`, their exact package/file URLs and version,
  per-file SHA-256 hashes, and MIT license, plus a frozen `icons.js` registry with exactly the
  four `DESKTOP_UI.md` foundation glyph names at GUI Break 1. A production helper accepts only
  a registered glyph and `sm`/`md`/`lg`, creates no SVG/path markup, and returns
  an inert decorative element with fixed classes; unknown, path-shaped, URL,
  case-variant, and prototype-key inputs are refused without DOM mutation.
  Static evidence finds no registry mutation API, remote/data URL, dynamic SVG
  string, data-derived mask/class/path, or icon asset outside the package-owned
  directory. XML evidence rejects scripts, event-handler attributes,
  `foreignObject`, external `href`, and any CSS `url()`. `tokens.css` is the
  sole icon-size owner at exact 16/20/24 px and `components.css` is
  the sole mask/alignment/interaction owner. In the clean-installed-wheel
  gallery the same glyph has the exact three computed sizes and inherits its
  surrounding `currentColor` in light, dark, forced-colors, interactive, and
  disabled states, while visible text or an accessible control name still
  carries meaning. *Not satisfied by* an icon font, CDN/package-manager runtime,
  inline/generated SVG, a mutable map, concatenating a request value into a
  class or URL, testing a copied source-tree asset, or treating an icon as the
  only status cue. Later slices may extend the registry only through reviewed
  source, asset/provenance, packaging, and test changes.

- **SH-G-15 — OPEN: the complete headed runtime is version-bound and
  contained.** This is distinct from SH-G-8's Python transport-custody graph
  and BR-G-45's subject-scaled terminal artifacts. A parent instrument outside
  the headed Job begins sampling when the root is assigned, before window
  startup, and records absolute cold peak plus a fixed post-fixture settled
  plateau without subtracting an idle baseline. In the same loaded process,
  repeated ordinary fixtures and a separately declared long fixture use equal
  fixed pre/post quiescent windows to record warm marginal peak and plateau
  growth. Private bytes, process count, thread count, and handle count retain
  independent absolute and growth predicates rather than collapsing into one
  friendly total.

  Every sample records Job membership and, for each member, PID plus creation
  time, executable/role, private bytes, threads, and handles. Member birth,
  exit, or role change remains visible; an unreadable live member, missing root,
  PID-reuse ambiguity, or asymmetric pre/post topology refuses the affected
  evidence. Raw telemetry is streamed or held in fixed bounded buffers outside
  the Job. The child performs no whole-evidence serialization during a measured
  window, and final artifact assembly begins only after the last post-fixture
  plateau closes. Test-only in-Job state is declared and bounded rather than
  subtracted after measurement.

  Calibration fixes the fixture counts/durations, plateau statistic, ceilings,
  and a predeclared headroom rule in one commit. A later commit runs independent
  holdouts without retuning them. Each accepted artifact binds the exact source
  and wheel, Windows build, CPU/RAM profile, CPython, SQLite, pywebview,
  pythonnet/CLR, Bottle, and WebView2 identities. A changed runtime tuple has no
  inherited pass: its limits and evidence are explicitly reaffirmed or
  recalibrated through the same calibration/freeze/holdout sequence. **No
  calibration limits or holdout exist yet.** The 2026-08-13 67,375,104-byte
  whole-Job delta is diagnostic input only because that run lacks cold absolute
  and settled plateaus, symmetric repeated/long warm windows, decontaminated
  telemetry, and frozen independent limits. *Not satisfied by* one baseline
  delta, aggregate-only PID sampling, serializing growing evidence in the
  measured child, choosing a limit from its own holdout, treating calibration
  as validation, dropping thread/handle/topology growth, or silently carrying a
  pass across a version change.
  Under the measurement authority in `DEFENSE.md` §7 this is a version-bound
  empirical Tier 3 gate. Tier 0 reasoned targets or diagnostic whole-Job runs
  may guide design, but cannot close it.

SH-G-11 through SH-G-13 are cross-slice: their foundation — tokens in three
themes with contrast, Mica apply/degrade, and reduced-motion with the motion
tokens — is proven on GUI Break 1's gallery. Slice 4 closes the shared-shell
clauses (no raw color in its renderer, tokenized translucent content cards,
and no animation on row recycling); the production plan/inventory clauses
finalize with their renderers in Slices 5 and 6.
SH-G-14's closed registry and package foundation lands entirely in GUI Break 1;
later glyph choices are ordinary Slice 4-7 surface work and must not reopen its
runtime or asset-authority boundaries.

The concrete homes: `tests/interfaces/web/test_slice1_headed.py` (headed
SH-G-1/2/5/6/10 and BR-G-31 activation),
`tests/interfaces/web/test_paths.py` plus
`tests/interfaces/web/test_headed_native.py` (ordinary and static SH-G-2),
`tests/interfaces/web/test_logging_config.py` (ordinary/child-process SH-G-3
logging clauses) plus `tests/interfaces/web/test_transport_headed.py` (SH-G-3's
real renderer/dispatched-body clauses),
`tests/interfaces/web/test_commands.py`, `test_transport.py`, `test_slots.py`,
`test_frontend_static.py`, and `test_transport_headed.py` (split ordinary and
headed BR-G-32 transport evidence),
`tests/test_version.py` (SH-G-4),
`tests/interfaces/web/test_wheel_assets.py` (ordinary SH-G-6),
`tests/interfaces/web/test_frontend_static.py` (SH-G-7),
`tests/interfaces/web/test_visible_sequence.py` (BR-G-34 and BR-G-2's Stage 6
structure clause),
`tests/interfaces/web/_tree_window_fixture.py` (test-only production-chain
window manifest shared by Node and installed WebView2 evidence),
`tests/interfaces/web/test_shell_headed.py` (installed-wheel headed SH-G-7),
`tests/interfaces/web/test_drain.py` (SH-G-8 deterministic, linger, and
overflow fixtures), `tests/interfaces/web/test_bridge_event_benchmark.py`
(ordinary streamed-evidence, event/diagnostic-separation, direct-Job, and
retained-state accounting checks),
`tests/interfaces/web/test_bridge_transport_custody.py` (frozen corpus,
production-deque, source/runtime/digest-authority, and exact-shape contracts),
and the opt-in
installed-wheel command
`.\.venv\Scripts\python.exe tests\bridge_event_benchmark.py --output "$env:TEMP\namisync-bridge-event-benchmark.json"`
(SH-G-8 event evidence). The clean-commit calibration reproduction command is
`.\.venv\Scripts\python.exe -I -S tests\bridge_transport_custody.py calibration --output "$env:TEMP\namisync-bridge-transport-custody-calibration.json"`;
its durable three-process calibration-a artifact is
`tests/interfaces/web/sh_g_8_transport_calibration.json`. That artifact is the
normative measurement; `tests/interfaces/web/sh_g_8_transport_ceiling.json`
separately freezes the 1,966,080-byte ceiling. The clean-commit holdout command
is `.\.venv\Scripts\python.exe -I -S tests\bridge_transport_custody.py holdout --output "$env:TEMP\namisync-bridge-transport-custody-holdout.json"`;
`tests/interfaces/web/sh_g_8_transport_holdout.json` and
`tests/interfaces/web/test_bridge_transport_custody_holdout.py` are the durable
accepted evidence,
`tests/interfaces/web/test_history_pager.py` (SH-G-9),
`tests/interfaces/web/test_single_instance.py` (ordinary/static SH-G-10),
`tests/interfaces/web/test_design_tokens.py` (ordinary SH-G-11),
`tests/interfaces/web/test_materials.py` plus
`tests/interfaces/web/test_materials_headed.py`
(ordinary and real-stack SH-G-12),
`tests/interfaces/web/test_motion.py` (ordinary SH-G-13), plus
`tests/interfaces/web/test_icons.py` and
`tests/interfaces/web/test_component_gallery_headed.py` (installed-wheel
headed SH-G-11/13/14). SH-G-15 implementation must add an ordinary artifact
validator under `tests/interfaces/web/` and a separate opt-in installed-wheel
runtime command under `tests/`; this list and the command become exact in the
same change rather than borrowing SH-G-8's `passed` field.
A gate test may live elsewhere
only when the owning slice updates this list in the same change.
Release evidence records the collected `test_sh_g_*` node ids alongside the
BR-G ids; the cleared-`addopts` release command, not the default headless suite,
is the evidence that no headed gate was deselected.

Final gate closure is explicit; a cross-slice gate remains open until its last
clause lands:

| Final closure | Shell gates |
| --- | --- |
| Phase 0 | SH-G-4 |
| Slice 1 | SH-G-1, SH-G-2, SH-G-5, SH-G-6, SH-G-10 |
| Slice 2 | SH-G-3 |
| Slice 3 | SH-G-8 closed: linger/corpus/runner, calibration-a, frozen 1,966,080-byte ceiling, and independent holdout-b all passed |
| GUI Break 1 | SH-G-11, SH-G-12, SH-G-13 (foundation), SH-G-14 |
| Slice 4 | SH-G-7 |
| Slice 6 | SH-G-11, SH-G-12, SH-G-13 (production surfaces) |
| Slice 7 | SH-G-9 |
| Slice 8 | SH-G-15 remains open pending version-bound calibration, frozen limits, and independent holdouts |

## 6. Slice-to-gate map

This table maps shell delivery order to the sole BR-G definitions in
`M1_BRIDGE.md`; it does not redefine them.

| Delivery checkpoint | BR-G dependency | Shell status |
| --- | --- | --- |
| Phase 0 | prerequisites for BR-G-19/31/32 | complete |
| Slice 1 | BR-G-19 and BR-G-31 host clauses | complete |
| Slice 2 | BR-G-32 transport, picker, origin, and static-sink clauses | complete, including installed real-WebView2 browser witnesses; later DOM clauses remain open |
| Slice 3 | BR-G-33, BR-G-41 transport/lifecycle foundations, and event/transport-custody portion of BR-G-42 | complete, including accepted independent holdout-b; full BR-G-41 and other BR-G-42 rows remain on later owning slices |
| GUI Break 1 | presentation foundations for later BR-G surfaces | complete |
| Slice 4 | BR-G-2 Stage 6 clause, BR-G-32 generic-tree-sink portion, and BR-G-34 | complete |
| Cosmetic thaw/refreeze | BR-G-46 | complete before Slices 5–7 |
| Slice 5 | BR-G-32 plan-DOM portion, BR-G-35 through BR-G-37; plan portion of BR-G-42 | pending |
| Slice 6 | BR-G-32 inventory-DOM closure, BR-G-22, BR-G-23, BR-G-38, BR-G-39; inventory portion of BR-G-42 | pending |
| Slice 7 | BR-G-40, BR-G-41, BR-G-45; history portion of BR-G-42 | pending |
| GUI Break 2 | holistic `DESKTOP_UI.md` visual/accessibility review | pending after Slice 7 |
| Slice 8 | BR-G-43, BR-G-44, and shell-owned SH-G-15 | pending |

The explicit-`Gap`-only recovery decision and the command-specific
`start_plan` revision decision are ratified in `M1_BRIDGE.md`; their named
regressions have landed. A numeric sequence hole alone does not reopen recovery.
The fixed 150 ms linger and focused regressions have also landed.
Benchmark/accounting support now streams manifested evidence, assembles the
artifact after the child exits, reports whole-runtime memory without an
acceptance predicate, and sizes transport roots separately from terminal
results. The frozen/disjoint realistic corpus and production-path runner now
prove the exact built-in-deque roots, quiescent per-task 128/64/64 no-`Gap`
shape and ordered cleanup, terminal path cut, and clean source/dependency/runtime/digest
authority. The committed calibration-a artifact records the normative
1,376,690-byte ordinary and 1,534,946-byte exact-maximum union measurements.
The separate contract freezes the 1,966,080-byte ceiling, and independent
holdout-b passes at 1,351,794 ordinary and 1,513,014 exact-maximum bytes.
The frozen historical v1 SH-G-8 and BR-G-42 event/transport-custody claim is
closed; current-v4 measurement evidence consists only of its diagnostic event
rerun and Tier-1 current-source custody drift characterization, as dispositioned in
`M1_BRIDGE.md`. Other BR-G-42 rows remain on their owning slices. The valid
2026-08-13 run passed its duration/rate/event/latency/shutdown predicates, but
its whole-Job delta is neither corrected transport-custody evidence nor a
version-bound SH-G-15 containment result. BR-G-45 and SH-G-15 remain separately
open; no gate inherits a limit or pass from that run.

## 7. Contract pointers and change control

| Concern | Sole authority | Shell responsibility |
| --- | --- | --- |
| Bridge protocol, errors, identity, recovery, lifecycle, and BR-G gates | `docs/M1_BRIDGE.md` | preserve one wrapper/dispatcher/drain placement and slice dependencies |
| User-facing behavior, visual language, material, palette, icons, and motion | `docs/DESKTOP_UI.md` | place/package the declared assets at the assigned slice |
| Layering and service/host ownership | `docs/ARCHITECTURE.md` | keep the desktop an adapter over `NamiSyncService` |
| Product scope and deferrals | `docs/FEATURES.md`, `docs/M1_PLAN.md` | schedule only the active Stage 6 work |
| Packaging and release evidence | this file, BR-G-43/44 in `docs/M1_BRIDGE.md` | build from the installed/frozen artifact and run every named gate |

A bridge change updates `M1_BRIDGE.md` and its BR-G evidence in the same
atom. A visual change updates `DESKTOP_UI.md` and its SH-G evidence together.
This file changes only when delivery order, host/package placement,
launcher/packaging policy, or a shell gate changes.
