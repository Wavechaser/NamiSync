# M1 Desktop Shell Delivery Plan

Status (2026-08-04, implementation updated 2026-08-12): plan and progress for
the remaining M1 desktop shell. The 2026-08-06 revision folded in the
bounded-history and terminal-cleanup contracts now recorded in `HISTORY.md`
and `DISPATCHER.md` and added sections 5-8; the 2026-08-07 revision settles
single-instance identity,
the database file-pair matrix, in-loop startup teardown, the normative CSP
gate, the GUI argument grammar, and constructor-only command composition; the
2026-08-08 revision adds the Fluent visual design language (§1.9), motion
(§1.10), and the two GUI Breaks that bound the visual work.
Stages 1-5.5, Phase 0, the WebView2 reality spike, and Slices 1-3 are complete.
The installed-wheel and real WebView2 gates now cover the secured product host,
bounded startup finalizer, nonblocking user-close/retry state machine, fixed
single-instance boundary, coordinated database refusal, exact three-command
transport, real native picker confinement, committed-origin refusal, and
hostile-text/privacy return path. The Slice 3 event drain, transactional
pre-schedule observation, bounded task registry, and reincarnation recovery are
implemented. GUI Break 1's token, component, icon, motion, and native-material
foundation is complete; Slice 4 is next. NamiSync remains version `0.1.0` until
M1 is complete. Finishing M1 makes the product beta-ready; any later version
change is a separate release decision.

## Standing

`M1_BRIDGE.md` remains the authoritative bridge semantics and BR-G acceptance
contract. `DESKTOP_UI.md` remains the user-facing desktop contract. This file
owns the implementation sequence, frontend/package layout, and release-work
placement for the shell. Its later entry-point and packaging decisions replace
the older statements that bare `nami-sync` opens the desktop or that no GUI
launcher is generated.

The shell does not move domain authority into JavaScript. The desktop remains
an adapter over `NamiSyncService`; the import law, reviewed-plan safety model,
process-local M1 lifetime, and all BR-G gates continue to apply.

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
    pywebview_runtime.py
    logging_config.py
    paths.py
    host.py
    appearance.py
    commands.py
    drain.py
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
        bridge.js
        render.js
        tree.js
        rail.js
        panels.js
        plan.js
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
`plan.js` and `inventory.js` keep the two vertical renderers disjoint;
`panels.js` owns only their shared panel frame. `tokens.css` holds the Fluent
design tokens (section 1.9), `components.css` the Fluent control set built on
them, and `app.css` layout only; surface renderers consume tokens and
components and define no color of their own.

At Slice 2 closure the exact shipped asset set is `index.html`, `app.css`,
`app.js`, `bridge.js`, and `render.js`; later entries in the target layout do
not ship until their owning slices. `render.js` owns the strict production
`textContent` sink. The browserless probes and headed `transport_gate/` page
remain under `tests/assets/` and are excluded from package data.
GUI Break 1 adds `tokens.css`, `components.css`, `icons.js`, and the exact four
SVGs plus source/license records under `assets/icons/`; its component-gallery
scenario remains test-only and absent from the wheel.

The production host resolves its index from package resources. A
Python-construction-only override accepts an absolute local index path for
headed tests so the test page and production assets can be assembled under one
temporary root. The production launcher never accepts that override from argv,
the bridge, or page data, and test assets are never package data.

### 1.7 Fixed virtual row geometry

All virtualized plan and inventory rows use one CSS-pixel height expressed in
exactly two authored declarations:

```css
:root { --row-h: 28px; }
```

```javascript
export const ROW_H = 28;
```

An ordinary test parses the two declarations and asserts integer equality.
Row CSS fixes border-box height, min/max height, vertical margins, and
single-line overflow. A headed check measures representative hostile and long
rows so matching constants cannot hide accidental variable DOM height.

### 1.8 One browser bridge wrapper

Only `assets/bridge.js` may reference `window.pywebview`. It owns readiness,
schema version, transport request ids, mutation command ids, timeout classes,
response validation, and bridge-reincarnation recovery. A static test enforces
the single reference site.

`request_id` identifies one transport attempt. `command_id` identifies one
receipted user gesture and survives uncertain delivery and retry. A retry always
uses a new request id. A receipted command reuses its command id and exact
command payload; it carries a revision only when that command was formed against
a revisioned server view. Therefore Slice 2's `start_plan` requires a command id
but no revision, while `pick_folder` requires neither. Later selection and
inventory mutations carry the revision required by their owning view contract;
the bridge does not invent a blanket revision field for every mutation. Drains
recover from the last sequence the client accepted rather than using a mutation
receipt. Repeated
`pywebviewready` events install no duplicate listeners and rearm at most one
drain per task.

The Python `BridgeDispatcher` instance exposes only `dispatch`; every other
instance member remains underscore-prefixed because pywebview recursively
walks and reads public attributes during injection.

### 1.9 Visual design language

NamiSync presents as a Fluent 2 (Windows 11) desktop app. This section fixes the
design language; the pixel-level result is tuned in the GUI Breaks (section 2),
not preselected here.

- **Type and frame.** Body text is Segoe UI Variable; paths and hashes use
  Cascadia Mono/Consolas. Both are Windows 11 system fonts, so no font ships.
  M1 keeps the standard OS window frame and gets Fluent chrome from native
  materials; a frameless custom caption — with its caption-button and
  window-drag reimplementation — is deferred post-M1 so no new native surface
  needs re-proving for the beta.
- **Native materials.** Mica (`DWMSBT_MAINWINDOW`) is the whole-window base,
  applied by DWM on the top-level HWND at the same UI-thread hook Slice 1 uses
  for guard attachment, with an immersive dark title bar; the WebView2 controller
  background and the page base are transparent so the material shows through
  everywhere it is not covered. Content does not hide Mica edge-to-edge — it sits
  in opaque Fluent *cards* floating on the Mica base, and Mica stays visible in
  the seams: the title bar, the task-rail and unselected-tab backgrounds, and the
  gutters and margins around cards. Cards are opaque for readability and because
  compositing a material behind a virtualized scrolling list is a rendering and
  performance trap, so the plan and inventory trees render inside an opaque card
  while their surrounding gutter stays Mica. No Acrylic in M1; menus and dialogs
  are opaque, and a later CSS `backdrop-filter` acrylic on those overlays is a
  localized `components.css` change, not a re-architecture. High contrast disables
  Mica and honors the system high-contrast palette; a system without the material
  (pre-22H2) or a transparency failure degrades to an opaque Fluent neutral base,
  never a broken see-through window.
- **Tokens and theme.** Neutral and accent roles resolve through Windows/CSS
  system colors until another authored color is explicitly approved; the type,
  spacing, 4px-based radius, elevation, and motion scales live in `tokens.css`
  as theme-agnostic CSS variables. M1 follows the system light/dark theme and
  honors high contrast; the accent color is read from Windows and pushed to the
  token variables, and both theme and accent changes are observed and re-pushed.
  The Microsoft Fluent 2 Figma kit and Microsoft's published Fluent tokens are
  the reference for non-color scales and component behavior; no Fluent code is
  imported (section 1.6 forbids the toolchain that would need).
  NamiSync's authored status/operation palette is a separate, exact input owned
  only by that file:

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

  These are exactly 13 palette primitives; yellow and purple intentionally have
  no authored `light` primitive at GUI Break 1. Adding another hardcoded or
  derived color value, including a future yellow/purple `light`,
  is a deliberate design change that must first be discussed with the product
  author and then land through this token contract and its evidence. The
  current implementation must not silently manufacture or disguise one through
  `color-mix()`, alpha/transparency, another color function, or an alternate
  alias.
  Semantic status and operation aliases in `tokens.css`, never palette names,
  are the contract consumed by controls and surfaces. The `main`/`dark`/`light`
  labels identify authored swatches, not theme assignments: GUI Break 1 chooses
  light- and dark-theme semantic pairs only after visual and numeric contrast
  checks. Under Windows forced colors, semantic aliases resolve to appropriate
  system colors rather than forcing this palette.
- **Components.** Because there is no framework or bundler, the control set is a
  compact hand-authored Fluent 2 CSS system in `components.css` on those tokens:
  button, dropdown, tri-state checkbox, determinate and indeterminate progress,
  text input, toggle, chips, list/tree row, card, dialog, context menu, and the
  Sync|Integrity segmented control. Each control carries its rest, hover,
  pressed, disabled, and focused states. Surface renderers consume tokens and
  components and define no color of their own.
- **Icons.** Microsoft Fluent System Icons are the default source. GUI Break 1
  vendors only the four regular 20 px foundation glyphs it needs to prove the
  system (`checkmark_circle`, `dismiss_circle`, `warning`, and `info`) from one
  pinned `@fluentui/svg-icons@1.1.334` package, retaining the upstream
  filenames, per-file SHA-256 hashes, MIT license, exact package/file source
  URLs, and package version under `assets/icons/`.
  `icons.js` owns one frozen code-only registry whose public names are visual
  glyph names, not workflow or status policy. A registry entry selects one
  fixed CSS class; the class selects one fixed local SVG as a CSS mask.
  `tokens.css` owns only the shared `--icon-size-sm: 16px`,
  `--icon-size-md: 20px`, and `--icon-size-lg: 24px` sizes. `components.css`
  owns mask alignment, sizing classes,
  `background-color: currentColor`, and interaction/disabled behavior. The
  helper creates only an inert span with allowlisted classes: it never emits or
  parses SVG markup, accepts a URL/path, constructs a class or asset name from
  data, fetches remotely, or exposes runtime registration. An unknown glyph or
  size is refused instead of falling back. Icons are decorative by default and
  accompany visible text; an icon-only control must own an accessible name.
  Later slices add the exact surface glyphs and mappings as ordinary source
  changes to the registry, CSS, provenance, package manifest, and tests.
- **Information architecture.** The rail-plus-panel layout, task cards, the
  Sync|Integrity toggle, and the setup-form-versus-summary flow follow
  `DESKTOP_UI.md` and the `ui_mockup/` reference. The mockup is a look and IA
  reference only — it is dark-only, simulates menus and caption buttons, and
  sources tokens from a removed Qt file — so it is re-authored against the real
  tokens and bridge/command/view contracts rather than grafted in.

### 1.10 Motion

Fluent motion is a system, not per-element choreography. Duration steps and the
Fluent easing curves live in `tokens.css` as CSS variables transcribed from the
Fluent motion spec; state transitions, expand/collapse, progress, and dialog
entrance/exit are plain CSS on those tokens (WebView2 is full Chromium, so
nothing is held back). Two guardrails are normative:

- `prefers-reduced-motion` is honored — non-essential motion reduces or stops,
  matching the system setting.
- No animation is bound to virtualized-row recycling. Rows are created and
  destroyed by scrolling, so animating their insertion or removal produces jank
  and flicker; motion lives at the panel, control, and discrete-state level, not
  on the plan or inventory row lifecycle.

The exact choreography is felt, not specified, and is tuned in the GUI Breaks.

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
   create BridgeDispatcher(document=pending_state)
   create_window(local index path, js_api=dispatcher)
   start_edge_chromium(http_server=True, private_mode=True,
                       storage_path=paths.webview2)
       initialized -> renderer check
                   -> ExactOrigin.from_url(window.real_url)
                   -> bind pending document origin exactly once
                   -> register synchronous before_load installer
       before_load -> UI thread -> record BrowserVersionString
                                -> attach native guards
       loaded      -> verify attached/no attachment_error
   ```

   Dispatch remains closed while document authority is pending or failed.
   Pywebview private window fields are not mutated to solve construction order.

   A failure before `start_edge_chromium` unwinds acquired state through one
   bounded finalizer: close the service if constructed, log any cleanup failure
   without replacing the original startup failure, shut logging down if
   configured, release the mutex, show the failure through the native reporter,
   and exit nonzero. The losing second instance never configures the rotating
   logger, so two GUI processes cannot rotate the same file.

   Two failures happen *inside* `start_edge_chromium` and converge on that same
   finalizer, because pywebview swallows event-handler exceptions and its
   decorated close can wait ~20 seconds for a window that was never shown:

   - **Initialized failure** (renderer or origin, which pywebview invokes
     *before* it creates the native window): record the renderer/origin
     failure, return `False` to abort creation, let `start_edge_chromium`
     return, and do **not** call `window.destroy()` — no native window exists.
   - **Guard or loaded failure** (native attachment on the UI thread): store the
     sticky failure, mark the host startup-refused, and call `window.destroy()`
     exactly once. The `loaded` watchdog stores state and destroys rather than
     raising. Destruction happens first here, to escape the GUI loop.

   After `start_edge_chromium` returns, both in-loop paths run the finalizer
   above. Because dispatch never opened, `service.close()` should return a
   complete shutdown view; an incomplete result or exception is logged, but
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
   attempt, and there is no force-destroy path. The startup-refused phase from
   step 5 is the one exception: its closing handler recognizes that phase and
   bypasses this veto/Retry machine entirely, letting the single startup
   `window.destroy()` fall straight through to the bounded finalizer. Slice 1
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

The following is the normative, implemented Slice 2 transport contract. Its
closure covers transport, picker, committed-origin refusal, static sinks, and
SH-G-3 logging/privacy; it does not claim the later plan or inventory DOM
portions of BR-G-32.

**Wire envelopes and limits.** The JavaScript wrapper sends one JSON string to
`dispatch(command_json)`. Its UTF-8 encoding must be at most 65,536 bytes before
JSON decoding. Duplicate object keys, non-finite numbers, malformed Unicode,
and missing or unknown fields at any defined object level are invalid. The v1
request has exactly these fields:

```json
{
  "schema_version": 1,
  "request_id": "0123456789abcdef0123456789abcdef",
  "command": "pick_folder",
  "payload": {"purpose": "source"}
}
```

`schema_version` is the JSON integer `1` (a Boolean is not an integer here).
Both transport `request_id` and mutation `command_id` match
`^[0-9a-f]{32}$`; a slot id matches `^slot-[0-9a-f]{32}$`. The wrapper mints a
fresh request id for every transport attempt. IDs are opaque and one ID kind is
never accepted in place of another.

A successful dispatch returns exactly:

```json
{
  "schema_version": 1,
  "request_id": "0123456789abcdef0123456789abcdef",
  "ok": true,
  "result": null
}
```

The response request id equals the admitted request. A failed dispatch returns
exactly:

```json
{
  "schema_version": 1,
  "request_id": null,
  "ok": false,
  "error": {
    "code": "invalid_request",
    "message": "The desktop request is invalid."
  }
}
```

`request_id` is echoed only after it independently passes its grammar;
otherwise it is `null`. The server error vocabulary is exact:

| `code` | Fixed `message` |
| --- | --- |
| `invalid_request` | `The desktop request is invalid.` |
| `unsupported_version` | `Restart NamiSync to load a compatible desktop page.` |
| `unknown_command` | `This desktop action is not available.` |
| `invalid_payload` | `The desktop action contains invalid data.` |
| `request_too_large` | `The desktop request is too large.` |
| `slot_unavailable` | `That folder selection is no longer available. Choose both folders again.` |
| `picker_unavailable` | `The folder picker could not open. Try again.` |
| `command_conflict` | `This action no longer matches its first attempt. Start the action again.` |
| `planning_refused` | `NamiSync could not start a plan for those folders. Review both folders and try again.` |
| `task_unavailable` | `That desktop task is no longer available.` |
| `drain_busy` | `That desktop task already has an event request in progress.` |
| `observation_conflict` | `That desktop task is already observing different work.` |
| `bridge_unavailable` | `NamiSync is closing or this desktop page is no longer trusted.` |
| `internal_error` | `NamiSync could not complete the desktop action.` |

Retry behavior belongs to the immutable command row and JavaScript wrapper,
not to data returned by a possibly failed handler. A structured server refusal
is definitive. Only uncertain transport delivery or `internal_error` from an
admitted receipted command may trigger that row's one same-command replay.
Messages contain no request body, command payload, real path, exception text,
traceback, Python type, or implementation detail. No command exception crosses
pywebview as its traceback-bearing native error value.

**The production allowlist is exactly two rows.** `payload` and `result` below
are exact schemas, not examples; no additional production command name or
placeholder handler lands in Slice 2.

| Command | Exact payload | Exact success `result` | Identity / revision | Timeout and retry |
| --- | --- | --- | --- | --- |
| `pick_folder` | `{"purpose":"source"}` or `{"purpose":"target"}` | user cancel: `null`; selection: `{"id":"slot-<32-lowercase-hex>","display":"<valid Unicode string>"}` | no `command_id`; no revision | interactive native operation; no client deadline and no automatic retry; a later user gesture is a new attempt with a fresh request id |
| `start_plan` | `{"command_id":"<32-lowercase-hex>","source_id":"slot-<32-lowercase-hex>","target_id":"slot-<32-lowercase-hex>","deletion_policy":null}` or the same exact key set with `"trash"` or `"additive"` | Slice 2: `{"request_id":"<32-lowercase-hex>","session_id":"<32-lowercase-hex>"}`; Slice 3 atomically expands it to `{"task_id":"task-<32-lowercase-hex>","request_id":"<32-lowercase-hex>","session_id":"<32-lowercase-hex>"}` | required `command_id`; no revision because this creates a session rather than mutating a revisioned view; Slice 3 retains the adapter-owned task id with the same command receipt | 30,000 ms response deadline; after uncertain delivery, bridge reincarnation, or `internal_error`, at most one automatic replay uses a fresh request id and the same command name, payload, and command id; a still-uncertain result exposes Retry, which retains that same command id |

`display` is presentation-only inert text; Python never accepts it back as
authority. `null` means use the service's current semantic deletion setting;
`mirror` is not accepted by this Slice 2 command. Automatic replay uses the
exact original payload. Service receipt identity is ultimately the resolved
source/target pair plus deletion policy: reusing a command id for different
resolved intent returns `command_conflict`, while the same resolved intent
returns the existing `start_plan` receipt. A timer expiring in JavaScript does
not cancel an admitted Python handler.

**Folder slots are bounded server authority.** Only the native picker may
insert a slot. Each entry retains the real path, its `source` or `target`
purpose, inert display text, and a monotonic expiry 30 minutes after insertion.
Lookup does not consume a slot and does not extend its expiry, so the same slot
pair supports a same-command retry while live. Before insert or lookup, expired
entries are swept. At most 32 unexpired entries exist. If insertion still finds
32, it evicts exactly the least-recently-used entry (slot id breaks a timestamp
tie); a successful lookup updates recency but never extends the fixed expiry.
`start_plan` resolves and snapshots the source and target entries under one lock
before invoking its handler: both must exist in the same observation, be
unexpired, and match their respective purposes, and only then are both marked
recently used. Fabricated, expired, evicted, or wrong-purpose ids all return the
same sanitized `slot_unavailable` error. No bridge request contains a path, and
no response makes `display` authoritative.

**Harness composition and deferrals.** `test_report` is not a production row.
The headed harness constructs a new immutable mapping from the production three
rows plus one test-owned `test_report` spec; its validator, handler, payload,
and result schema live under `tests/`, and product argv, environment, page data,
or bridge traffic cannot enable it. The harness uses the same v1 envelope and
production `bridge.js`, but its whole-scenario parent deadline owns test
timeout; there is no product `test_report` retry class.

The neutral browser primitive
`dispatchInteractive(command, payload, validator)` accepts only a 1--64 ASCII
lowercase-snake command name matching
`^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$` and a callable result validator, then makes
one transport attempt with no client deadline and no automatic retry. Payload
validation remains the selected Python command row's responsibility. Both
`pickFolder` and the constructor-only headed `test_report` client use this
primitive. It formats a request; it does not register or allow a command, so
Python's immutable constructor-supplied mapping remains the sole allowlist and
the `test_report` literal, payload schema, result schema, and handler remain
under `tests/` and absent from package data.

Slice 3 owns the event-drain command; Slice 5 owns plan-review, selection,
execution, and control commands; Slice 6 owns inventory commands; and Slice 7
owns settings, history, and lifecycle commands. Those names and payload schemas
are not reserved or allowlisted in Slice 2. A later command formed against a
revisioned view must carry that view's exact revision, while a later read or
mutation not formed against such a view does not invent one. The owning slice
must add its row, schema, receipt/revision rule, timeout, retry policy, and gate
together.

1. `commands.py` defines one explicit row per allowed command: exact payload
   validator, handler, read-only/mutating class, command-id requirement,
   revision requirement, and retry/timeout class.
2. Unknown versions, commands, fields, malformed ids, invalid Unicode, and
   oversized input are refused before handler invocation. Returned failures are
   sanitized and never expose Python tracebacks or filesystem authority.
3. `slots.py` retains real folder-picker paths server-side and returns only an
   opaque id plus display text. Fabricated and expired ids are refused.
4. Add the reusable headed harness. Test HTML and JavaScript live outside the
   package, are combined with production assets in an isolated temporary root,
   and run through the production host, server, origin guards, bridge wrapper,
   and render functions. Command composition is constructor-only, matching the
   spike's dispatcher, which privately snapshots its handler mapping:
   `commands.py` builds the immutable production command-spec mapping; the
   production host passes exactly that mapping; the harness builds a new
   immutable `production + test_report` mapping and passes it to the same
   dispatcher. There is no registration method and no `extra_commands` input
   from argv, environment, page data, or bridge traffic, and the `test_report`
   handler and its implementation stay outside package data. The existing
   production-table and build-output scan remains as defense in depth, but
   constructor-only composition makes the isolation structural rather than
   scan-enforced.
5. Each headed scenario runs in a child process with a hard parent timeout.
   JavaScript reports observed values through `dispatch("test_report")`; Python
   performs the assertion and destroys the window. NamiSync test code uses no
   `evaluate_js`.
6. The BR-G-32 hostile-text scenario takes its corpus from Python, crosses
   pywebview's `js_bridge_call` interpolation and `JSON.parse`, renders through
   the production `textContent` path, reads `.textContent` back in JavaScript,
   and returns it through `test_report`. Python asserts byte-for-byte equality.

Slice 2 closes the transport portion of BR-G-32. The production plan and
inventory DOM portions close only with slices 5 and 6. Split-level evidence is
named and owned as follows:

- `tests/interfaces/web/test_commands.py` owns discoverable ordinary
  `test_br_g_32_*` nodes for the exact immutable command table, full
  public-view codec manifest, and single browser-wrapper reference.
- `tests/interfaces/web/test_transport.py` owns ordinary `test_br_g_32_*` nodes
  for exact envelopes, strict pre-handler refusal, the 64 KiB boundary,
  sanitized failures, and start-plan receipt identity.
- `tests/interfaces/web/test_slots.py` owns ordinary `test_br_g_32_*` nodes for
  opaque purpose binding, fixed expiry, capacity/LRU, and atomic nonconsuming
  pair resolution. `tests/interfaces/web/test_frontend_static.py` owns the
  broadened packaged-asset sink scan under the same gate prefix.
- `tests/interfaces/web/test_transport_headed.py::test_br_g_32_hostile_text_crosses_real_return_transport_and_production_text_sink`
  owns the pinned-pywebview return path and production-`textContent` hostile
  corpus round trip through the constructor-only harness.
- `tests/interfaces/web/test_transport_headed.py` also owns separate
  `test_br_g_32_*` nodes for the real native picker path-confinement and
  independently committed off-origin dispatch-refusal clauses.
- `tests/interfaces/web/test_transport_headed.py::test_sh_g_3_headed_renderer_and_hostile_dispatch_are_logged_safely`
  compares the logged renderer to native `BrowserVersionString` and owns
  SH-G-3's real dispatched-body/path-sentinel privacy clause in a child host,
  while `tests/interfaces/web/test_logging_config.py` owns discoverable
  ordinary `test_sh_g_3_*` nodes for configuration/ownership, child-process
  startup records and console silence, rotation/Unicode, and exception hooks.
- Slice 5's production plan surface and Slice 6's production inventory surface
  add their own BR-G-32 named nodes; the Slice 2 nodes do not claim those DOM
  clauses early.

Slice 2's headed child uses an absolute physical local data/page root, unique
test-only window and mutex identity, a hard parent deadline, and a kill-on-close
Job Object. It drives the real native folder dialog without a foreground-forcing
API, localized-label lookup, or keystroke automation, proves the browser sees
only `{id, display}` while the service receives the selected paths, commits a
second loopback origin to prove
per-dispatch refusal without handler entry, and round-trips the hostile corpus
through production `renderText`. The harness extends the exact production
mapping only by constructor composition; `test_report` and every harness asset
remain absent from the wheel. Emitted records prove the native renderer version
and omit request bodies, real paths, hostile sentinels, tracebacks, exception
text, and the human-facing `NICKNAME`, closing SH-G-3.

The close-status hardening discovered while exercising repeated native loads is
also retained: each loaded document binds its current fixed `#host-status`
target before an asynchronous close attempt can render. A late worker never
queries a destroyed/replaced document, and a missing or failed presentation
target is logged without changing shutdown truth.

### Slice 3 - Event drain

Slice 3 adds exactly one production command, `next_events`, and expands
`start_plan`'s result with an adapter-owned task id. A task id matches
`^task-[0-9a-f]{32}$`; a session id, transport request id, command id, and drain
id each match `^[0-9a-f]{32}$`. These opaque kinds are not interchangeable.
The web adapter mints the task id once before the first plan admission and
retains `command_id -> task_id` beside its task state, so replay of the same
resolved `start_plan` intent returns the same task, request, and session ids.
Task identity does not enter the service, dispatcher, workflow request,
database, or compatibility protocol below the web adapter.

The Slice 3 production command table is therefore exactly the two Slice 2 rows
plus this row; there is no dormant control or presentation command:

| Command | Exact payload | Exact success `result` | Identity / revision | Deadline and retry |
| --- | --- | --- | --- | --- |
| `next_events` | `{"task_id":"task-<32-lowercase-hex>","session_id":"<32-lowercase-hex>","drain_id":"<32-lowercase-hex>","replay_from":null}` or the same exact key set with `replay_from` as the positive integer sequence of the first desired event | `{"task_id":"task-<32-lowercase-hex>","session_id":"<32-lowercase-hex>","drain_id":"<32-lowercase-hex>","updates":[<zero to 64 exact tagged updates>]}` | no `command_id`; no revision; every long-poll attempt has a fresh drain id and the server echoes it only in that attempt's success | the server waits at most 25,000 ms; the browser deadline is 30,000 ms; success, including an empty timeout result, arms a fresh drain; transport/protocol uncertainty recovers from the first sequence after the last accepted non-`Gap` event, while an explicit `Gap` recovers from its exact positive `first_missed_seq`; no response is retried or cached |

The `updates` array is ordered and contains only these exact tagged-union
members. `event` is the existing primitive `SessionEventView` JSON shape;
`record` is the existing primitive `SessionRecordView` JSON shape. Neither arm
accepts extra keys.

```json
{"update_type":"event","event":{"session_id":"0123456789abcdef0123456789abcdef","sequence":1,"at":"<UTC ISO-8601 string>","body_type":"StateChanged","body":{"state":"pending"}}}
```

```json
{"update_type":"record","record":{"session_id":"0123456789abcdef0123456789abcdef","kind":"plan","state":"completed","supports_pause":false,"created_at":"<UTC ISO-8601 string>","started_at":"<UTC ISO-8601 string or null>","ended_at":"<UTC ISO-8601 string or null>","result":"<OperationResultView object or null>"}}
```

`replay_from=null` is the ordinary drain. After transport/protocol uncertainty,
the positive value is the last accepted non-`Gap` sequence plus one. After an
explicit `Gap`, it is that event body's exact positive `first_missed_seq`, even
when earlier numeric holes were legal coalesced progress. It means the first
desired dispatcher sequence, not an acknowledgment. The response has no
cursor, receipt, `has_more`, or echoed replay value. The client advances its
local accepted sequence only after validating and accepting a non-`Gap` event.
It does not advance on `Gap` or on a terminal record. On an ordinary or
uncertainty-recovery response, a `Gap` stays visible, stops application of the
remaining updates, and arms recovery from its `first_missed_seq`. A recovery
response may instead start with the same `Gap` whose `first_missed_seq` equals
that attempt's `replay_from`; this is proof that prefix is no longer retained,
not another recovery trigger. The client keeps it visible, applies the
available tail after it, and does not loop. Any later/different `Gap` stops that
batch and becomes the next recovery point. Sequence numbers may jump
because `Progress` is replaceable in both dispatcher replay and the adapter
queue. A numeric hole alone is therefore legal and never triggers recovery.
Recovery never claims that a missing reliable event was restored: an explicit
`Gap` stays visible, available replay is applied, and the terminal record is
the final lifecycle truth.

`drain.py` owns one `TaskState` per adapter task. Its update queue has an exact
capacity of 64. It stores `SessionEventView | SessionRecordView`, never raw
dispatcher envelopes or workflow objects. On a new `Progress`, it removes an
older queued `Progress` and appends the new snapshot; if all 64 entries are
reliable, it discards the new progress. Before enqueuing a reliable update it
may remove queued progress, but it never removes or reorders reliable updates;
if 64 reliable entries remain, the observation sink blocks on capacity until a
drain or shutdown wakes it. A drain removes at most 64 entries in FIFO order,
returns immediately when any are available, otherwise waits on the task
condition for at most 25 seconds, and releases the one-drain claim in `finally`.
No `TaskState` lock spans a service call or JSON encoding. A second admitted
drain for the same task marks the incumbent long poll superseded, wakes it,
waits under the same 25-second server bound until that claim's `finally` has
released it, and only then returns `drain_busy`. The browser therefore has a
bounded proof that one re-arm cannot collide with the abandoned claim; it does
not spin or depend on a promise lost during bridge reinjection. An absent/closed task or mismatched
task/session pair returns `task_unavailable`; a competing attach/recovery
generation returns `observation_conflict`. Their messages are the fixed table
in Slice 2's envelope section.

Plan-start task identity is single-flight per command id and resolved intent.
After atomically resolving both slots, the first caller installs one provisional
`STARTING` command/task entry under the registry lock, then releases that lock
before calling the facade. Same-intent concurrent calls wait for that entry and
never call the facade; a different resolved source, target, or policy is
`command_conflict`. Success atomically binds the task to the returned request
and session ids and wakes every waiter, which returns those same three ids.
Facade, admission, or attach failure aborts the provisional task, wakes all
same-intent waiters with the same sanitized refusal, and removes the command and
task entries after those waiters release them. A later explicit attempt may
then create a new provisional task; no failed task id is exposed or retained.
If the facade returned a session but adapter binding itself cannot complete,
the adapter compensates outside its lock by unsubscribing, closing that session,
and dropping its plan before removing the provisional entry.

Normal-path continuity is established transactionally instead of guessed from
replay headroom. `NamiSyncService.start_plan` gains the keyword-only optional
`observation_sink` input, excluded from command-receipt identity, and
`SessionObserver` gains a resubscribe operation whose `from_sequence` is the
positive first desired sequence. The dispatcher remains domain-blind: its
optional admission attach callback receives only `(session_id, preopened
EventStream)` and returns an idempotent rollback callback. The dispatcher
prepares the record, hub, store row, and stream while the session is still
unpublished and unschedulable. The adapter callback adopts the stream into the
already-created task observation. Only after adoption succeeds does dispatcher
emit `PENDING` while the session remains unschedulable, then atomically publish
the session maps, append the pending entry, and notify the scheduler under the
admission/publication gates. Every exception from stream creation through
`PENDING` emission and atomic publication takes the same rollback path. The
attach callback is atomic from dispatcher ownership: it either returns the
rollback after a complete adoption, or raises only after self-reverting every
partial observer entry/thread it created. If adoption returned successfully,
dispatcher first invokes its rollback, which
signals stop, closes the adopted stream, and joins/removes that exact
observation; dispatcher then closes its remaining stream/hub ownership and
drops the store row. If attach raised before returning, dispatcher owns and
closes the stream directly. Cleanup never replaces the initiating exception. A
store-drop or cleanup failure is retained as dispatcher cleanup-pending
ownership, keeps shutdown incomplete, and can never make the row schedulable.
This seam contains no task vocabulary and
does not alter ordinary callers that omit it.

Recovery replaces only the task's observation generation. It clears queued
updates from the uncertain generation, calls the facade resubscribe outside the
task lock with `from_sequence=replay_from`, then adopts the replacement only if
the generation is still current. A concurrent recovery/attach is the named
`observation_conflict`; a slow facade call holds no task lock. The facade method
returns `SessionRecordView`: a nonterminal result means the replacement sink is
installed, while an already-terminal result installs no stream and the registry
enqueues that returned record itself. Close/recovery is serialized per task; if
close wins while the facade call is outside the lock, the registry unsubscribes
the just-installed session outside the lock before completing close. Terminal plan
sessions remain dispatcher-retained, including their replay and command
receipt, until task close. They are no longer live work and are not rendered as
an active rail entry, but early session close is forbidden because it would
destroy the recovery authority for a lost reliable or terminal bridge response.
Task close performs unsubscribe, `close_session`, and `drop_plan`; no drain
response cache, client acknowledgment, or second receipt is introduced.

`bridge.js` owns one generation-counted drain manager per task. Repeated
`pywebviewready` installs no duplicate listener and invalidates/re-arms at most
one drain for each retained task. Every attempt mints a drain id; stale promise
settlement cannot mutate the accepted cursor, render updates, or arm a second
loop. A valid success applies its tagged updates in order and then arms one
ordinary drain. Timeout, malformed/mismatched success, or bridge reincarnation
invalidates that generation and arms one recovery drain from the last accepted
non-`Gap` sequence plus one. An explicit `Gap` remains visible, ends that batch,
and arms recovery from its `first_missed_seq`, except for the matching leading
`Gap` of that recovery attempt, after which the retained tail is applied.
Acceptance of a terminal record stops that task's drain loop and suppresses all
further re-arms, even when it follows a matching recovery `Gap`. `drain_busy` is returned only
after the superseded incumbent has released its server claim, so one bounded
re-arm is enough; other structured refusals
are definitive and visible. No path relies on a raw numeric sequence hole.

Host shutdown follows one exact ownership order: reject new bridge admission;
close the drain registry and wake long-poll waiters and capacity-blocked sinks;
wait for already-admitted bridge handlers; unsubscribe every service
observation; then call `NamiSyncService.close()`. A task close uses the same
per-task wake-before-unsubscribe order. All waits are off the presentation
thread. Registry close marks provisional tasks closing but retains their
observations until the admitted-handler wait completes, so a close beginning
after attach cannot remove the observer before dispatcher publication.

Fault-inject lost reliable and terminal responses and repeat
`pywebviewready` while a drain is outstanding. This closes BR-G-33 and retains
XV-18 shutdown behavior.

The GUI is a recovery consumer, not a continuity consumer, but the normal path
must not lean on recovery: the task observation attaches before execution
admission starts the workflow, so an ordinary run inside the BR-G-42 envelope
sees no `Gap` with the production 128/64 replay/subscriber capacities.
`docs/DISPATCHER.md` still owns the continuity policy; bursts beyond that
envelope surface `Gap`, replay only the tail still retained, and reconcile
terminal truth. Missing reliable events remain visibly missing; recovery never
pretends full continuity or justifies invented replay headroom.

### GUI Break 1 - Establish the look (completed 2026-08-12)

A GUI Break is a deliberate stop to build and calibrate the visual system, not a
fraction of an assembly line. Break 1 builds the foundation every later surface
consumes and freezes the design language before the renderers exist, so Slices
4-7 render onto tokens and components rather than inventing their own. Its Lane P
authoring (tokens, components) may start as early as Slice 1 in parallel; its
scheduled home is here, immediately before the first frame, where the Slice 2
harness and Slice 3 drain exist to exercise it through the real host.

Deliverables:

1. The native material mechanism (Lane H): the DWM Mica backdrop, immersive dark
   title bar, and transparent WebView2 background at Slice 1's UI-thread hook,
   with the high-contrast and no-material fallbacks from section 1.9 and its own
   real-stack reality test. The security guards and construction order are
   unchanged by material application.
2. `tokens.css`: the Fluent color/type/spacing/radius/elevation and motion
   tokens, theme-agnostic, with system light/dark/high-contrast following and the
   accent read-and-observe plumbing. It also owns the exact 13 authored palette
   primitives from section 1.9 and semantic aliases for status meanings and
   operation categories. The authored swatch names do not prescribe theme
   pairing; the gallery settles those aliases through light/dark visual review
   and numeric contrast checks. Forced-colors aliases use Windows system colors.
3. `components.css`: the section 1.9 control set on those tokens, every state
   present, demonstrated on a non-shipped component-gallery page that runs
   through the production host and headed harness. The gallery is a dev/test
   artifact and never package data. Badges, banners, status pills, progress
   indicators, and related controls consume semantic aliases only. Gallery rows
   settle complete/success, failure/error, warning/degraded/incomplete, active,
   paused, canceled, mismatch, blocked/deferred, neutral/no-op, and every M1
   `OperationKind` value (`copy`, `update`, `move`, `move_update`, `recase`,
   `mkdir`, `trash`, `delete`, and `noop`), with visible text and
   icon/shape/state cues so color is never the sole carrier of meaning.
   The headed gallery runs from a clean installed wheel: production
   `index.html`, `tokens.css`, and `components.css` resolve through the installed
   package, and evidence records exact installed CSS bytes; only the gallery
   page/scenario code stays outside package data.
4. The minimal icon foundation from section 1.9: a frozen `icons.js` registry,
   the four pinned local Fluent SVG masks plus their source/license record, and
   gallery evidence that registry refusal is closed, every shipped asset is
   local and package-owned, all three size tokens compute exactly, and the same
   glyph inherits `currentColor` across light, dark, forced-colors, disabled,
   and interactive component states. Break 1 does not choose the later plan,
   inventory, history, or settings icon vocabulary.

Calibration is the tinkering part: get Mica, tokens, and components reading
correctly in all three themes and freeze the language. Time-box it to
language-and-gallery, not gold-plating — polishing against fixtures that must
then survive real data is wasted work. GUI Break 1 closes the SH-G-11/12/13
*foundation* — tokens, materials, and motion proven on the gallery — while each
gate's production-surface clause finalizes as the trees and renderers land.
It closes SH-G-14's icon-infrastructure boundary completely here; Slices 4-6
retain only the cross-slice production-surface clauses. Exit criterion:
tokens correct in light, dark, and high contrast;
the gallery covers every control state and the fixed icon foundation; Mica and
its fallback are proven on the pinned stack; the design language is frozen.
The completed checkpoint closes the SH-G-11/12/13 gallery/material foundation
and all of SH-G-14. It does not close SH-G-11/12/13's production-surface
clauses; those remain with the Slice 4–6 trees and renderers.

### Slice 4 - Presentation core and shell frame

Implement `visible_sequence.py` plus the minimal rail/panel/tree frontend.
Plan and inventory share the same pure flatten/window/search/filter/anchor
implementation over workflow-owned ordered node arrays. Enforce the 256-row
maximum and fixed row geometry. This closes BR-G-34 and the Stage 6 clause of
BR-G-2.

### Slice 5 - Sync surface

Land plan presentation, move annotations/ghosts, selection overlays, review
and destructive-confirmation flow, execution admission, paired progress item
identity, and indexed follow mode. The production plan renderer joins the
hostile-text headed round trip. Close BR-G-35 through BR-G-37 and the plan
portion of BR-G-42.

### Slice 6 - Inventory and integrity surface

Land cached inventory projections, `view_id` lifecycle, patch/acknowledgement
rules, five location-resolution states, recursive folder actions, warning
display, integrity modes, and per-window detail queries. The production
inventory renderer joins the hostile-text headed round trip. Close BR-G-22,
BR-G-23, BR-G-38, BR-G-39, and the inventory portion of BR-G-42.

### Slice 7 - Lifecycle, settings, and history

Land database-paged history, semantic-settings UI, cosmetic `ui-state.json`,
and one task-owned close/release seam that drops plan, selection,
execution/inventory detail, view/projection, session, and receipt artifacts
immediately for plan-only/already-terminal tasks or after terminal settlement
for busy work. Repeated create/close tests keep every registry bounded while
history remains. Also land full task detail in Slice 1's existing
shutdown-retry/incomplete presentation and normal single-instance activation
behavior. Close BR-G-40, BR-G-41, and the history portion of BR-G-42.

History paging follows the bounded readback contract exactly. A fresh event
traversal whose live cursor is ahead of durability returns the empty terminal
page — durable `through_seq`, unchanged `next_after_seq`, `has_more=False` —
and `history.js` treats that page as the end of that traversal, not a
retryable error. A later repair issues a fresh read that omits `through_seq`
and captures the new committed prefix; an explicit reversed fixed interval
remains invalid.

### GUI Break 2 - Visual cohesion (after Slice 7, before Slice 8)

With plan, inventory, history, and settings all real and on screen together,
Break 2 is the holistic taste pass that cannot happen earlier: cross-surface
spacing rhythm, motion choreography, empty/edge/error states, and the details
only visible with everything present. It precedes Slice 8 so packaging freezes a
finished look.

Its internals are deliberately loose because they are felt, not specified, but
its acceptance is explicit and mostly review-based: the result matches the
intended look, and — as the automatable share — contrast ratios meet the
accessibility bar on the token pairs and `prefers-reduced-motion` is honored
across every surface. SH-G-11 and SH-G-13 already assert those and are re-run
here over the now-complete surfaces. No new BR-G or SH-G gate is introduced;
Break 2 tightens what the earlier gates already pin.

### Slice 8 - Beta packaging and release closure

Release engineering follows a running vertical shell so it packages real
behavior rather than placeholders:

1. Add and commit the PyInstaller specification; unignore that named file.
   Add PyInstaller and `pyinstaller-hooks-contrib` as development dependencies.
   Use the pywebview and pythonnet `pyinstaller40` hooks and collect only the
   NamiSync web asset package. Run the host/hostile-page smoke test from the
   frozen artifact.
2. Add a resolved Windows build lock or constraints file. Release artifacts
   are built from that environment, not from a fresh floating resolution.
3. Add CI for headless pytest, import boundaries, wheel contents, and frozen
   construction. Real headed gates require an interactive Windows runner or
   recorded release-machine execution; a noninteractive hosted runner is not
   treated as equivalent.
4. Add `THIRD_PARTY_NOTICES.md`, required dependency license texts, visible
   binary-distribution license material, and clear directions from each binary
   release to the exact Corresponding Source tag/commit and build scripts.
   The release checklist uses GPLv3 section 6d's network-source path beside the
   binary download rather than making a section 6b three-year written offer.
5. Rewrite active desktop documentation as-built, update README status/index/
   limitations/changelog, re-status `ui_mockup/`, and close BR-G-43/BR-G-44.

M1 beta artifacts may be unsigned. Release notes publish SHA-256 hashes,
identify the exact source commit, explain the expected unknown-publisher
warning without telling users to disable Windows protections, and disclose
that enterprise policy or Smart App Control may block unsigned code. Paid
signing and Microsoft Store distribution remain post-M1 decisions.

The M1 beta does not bundle or automatically run the Evergreen WebView2
Bootstrapper. Windows 11 remains the supported target; missing WebView2 is
refused read-only with an official installation direction. Bundling the
bootstrapper is reconsidered with a real installer or an explicitly tested
Windows 10 support decision.

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
  measurement matching `ROW_H`. *Not satisfied by* scanning a hand-maintained
  file list that is not derived from the packaged asset set, or by asserting the
  meta element's presence without its exact content value.
- **SH-G-8 — The drain attaches before work starts.** A test proves the task
  observation is subscribed before execution admission starts the workflow,
  and no `Gap` occurs inside the BR-G-42 normal envelope; a fault-injected
  burst beyond that envelope surfaces `Gap`, resumes from the retained replay
  tail when available, and reconciles terminal truth without claiming the
  missing reliable events were recovered. *Not satisfied by* attaching after
  start, relying on replay for the normal path, or hiding loss behind terminal
  recovery.
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
  high-contrast. It contains exactly the 13 authored `--palette-*-main|dark|light`
  primitives from section 1.9, with no invented yellow/purple `light` value, and
  maps them through status- and operation-named semantic aliases. Headed gallery
  evidence records computed light/dark pairs and visible non-color cues for
  complete/success, failure/error, warning/degraded/incomplete, active, paused,
  canceled, mismatch, blocked/deferred, neutral/no-op, and every M1 operation
  type — exactly `copy`, `update`, `move`, `move_update`, `recase`, `mkdir`,
  `trash`, `delete`, and `noop`; computed light/dark checks require at least
  4.5:1 for normal text and 3:1 for large text, non-text indicators, and
  focus/control boundaries. Forced-colors evidence proves those aliases use
  system colors instead of the authored palette. A static ownership scan proves
  raw color literals and
  direct `--palette-*` consumption occur only in `tokens.css`: neither
  `components.css` nor any Slice 4-7 stylesheet/renderer may contain raw colors
  or consume a palette primitive directly. *Not satisfied by* a single-theme
  token set, treating a `light` primitive as an automatic light-theme foreground,
  color-only status meaning, adding or deriving/disguising a yellow/purple light
  swatch without the required product-author decision and same-change contract,
  token, and evidence update, or
  a scan that allows inline color in `components.css` or a surface module.
  The headed gallery resolves production `index.html`, `tokens.css`, and
  `components.css` from a clean installed wheel and records their exact bytes;
  a source-tree stylesheet or copied/reimplemented component sheet is not
  release evidence. The gallery page itself remains tests-only and absent from
  the wheel.
- **SH-G-12 — Native materials apply or degrade, never break.** On a capable
  system the DWM Mica backdrop and immersive dark title bar are applied and the
  WebView2 background is transparent; Mica shows through the intended seams —
  title bar, rail, and card gutters — while the virtualized plan/inventory tree
  renders on an opaque card rather than compositing the material behind scrolling
  rows; under high contrast Mica is disabled and the high-contrast palette is
  honored; on a pre-material system or an injected transparency failure the
  window falls back to an opaque Fluent neutral base.
  Material application changes neither the security guards nor the construction
  order. *Not satisfied by* a documentation lookup, a mock window, or a test that
  never exercises the fallback.
- **SH-G-13 — Motion honors the guardrails.** With `prefers-reduced-motion` set,
  non-essential transitions reduce or stop; a static/DOM check proves no
  animation or transition is bound to virtualized-row creation or removal in the
  plan or inventory tree. *Not satisfied by* asserting the media query exists
  without a reduced-motion render, or by checking only a non-virtualized list.

- **SH-G-14 — Icons are local, closed, and token-colored.** The installed wheel
  contains the exact four pinned Fluent regular SVGs from
  `@fluentui/svg-icons@1.1.334`, their exact package/file URLs and version,
  per-file SHA-256 hashes, and MIT license, plus a frozen `icons.js` registry with exactly the
  four section 1.9 glyph names at GUI Break 1. A production helper accepts only
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

SH-G-11 through SH-G-13 are cross-slice: their foundation — tokens in three
themes with contrast, Mica apply/degrade, and reduced-motion with the motion
tokens — is proven on GUI Break 1's gallery, while their production-surface
clauses (no raw color in a surface renderer, the virtualized tree on an opaque
card, and no animation on row recycling) finalize as `tree.js` and the
plan/inventory renderers land in Slices 4-6.
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
`tests/interfaces/web/test_drain.py` (SH-G-8),
`tests/interfaces/web/test_history_pager.py` (SH-G-9),
`tests/interfaces/web/test_single_instance.py` (ordinary/static SH-G-10),
`tests/interfaces/web/test_design_tokens.py` (ordinary SH-G-11),
`tests/interfaces/web/test_materials.py` plus
`tests/interfaces/web/test_materials_headed.py`
(ordinary and real-stack SH-G-12),
`tests/interfaces/web/test_motion.py` (ordinary SH-G-13), plus
`tests/interfaces/web/test_icons.py` and
`tests/interfaces/web/test_component_gallery_headed.py` (installed-wheel
headed SH-G-11/13/14).
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
| Slice 3 | SH-G-8 |
| GUI Break 1 | SH-G-11, SH-G-12, SH-G-13 (foundation), SH-G-14 |
| Slice 4 | SH-G-7 |
| Slice 6 | SH-G-11, SH-G-12, SH-G-13 (production surfaces) |
| Slice 7 | SH-G-9 |

## 6. Contract and Policy Watchlist

Each row names a policy that must not drift silently, the authority that owns
it, and the action any change requires. "Rerun" means the named gates run
against the changed configuration before the change lands.

| Policy | Authority | On change |
| --- | --- | --- |
| 256-event/1-MiB/one-second history window policy | `docs/HISTORY.md` | Rerun the documented 50-run/1,000,000-item benchmark and all its gates |
| 128/64 replay/subscriber capacities; no invented replay headroom | `docs/DISPATCHER.md` | UI/load evidence or a readiness-handshake design, never a constant bump |
| `pywebview==6.2.1`, `pythonnet==3.1.0`, `clr_loader`, Bottle floor, return transport | Section 1.2 | Rerun the native reality and hostile-text gates (BR-G-30/31/32 family) |
| Windows `netfx` runtime path and `PYTHONNET_RUNTIME` conflict refusal | `docs/DESKTOP_UI.md` | Re-probe and update the shared prerequisite check |
| CSP normative directive string (byte-for-byte), exact-origin, and navigation/popup guards | `docs/M1_BRIDGE.md` | Change the normative string and SH-G-7's expected literal together; rerun BR-G-31/BR-G-32 headed scenarios |
| `private_mode=True` with explicit `storage_path` | Section 1.3 | Headed retest of the storage branch on any pywebview upgrade |
| `namisync.log` header, level/propagation ownership, rotation, Unicode fallback, and privacy boundary | Section 1.4 | Rerun SH-G-3 and its child-process tests |
| Product/distribution version remains independent of schema, protocol, policy, contract, dependency, and runtime versions | Section 1.5 and each owning module | Bump and test only the affected owner; never create a central version registry |
| Bridge v1 envelopes, ID grammar, 65,536-byte cap, two Slice 2 command rows, fixed errors, and slot limits | Slice 2 normative transport target | Change `M1_BRIDGE.md`'s mirrored boundary and the BR-G-32 split evidence in the same atom; rerun XV-19 |
| `BridgeDispatcher` exposes only `dispatch` | Section 1.8 | Underscore the new member and keep the static test passing |
| Two-declaration `ROW_H` equality | Section 1.7 | Keep the parse test and headed measurement passing |
| Import-linter layers including `launcher` | `pyproject.toml` | `lint-imports` stays in the release command |
| Reliable readback semantics: sparse inclusive `through_seq`, empty terminal page | `namisync/interfaces/service.py`, `docs/HISTORY.md` | Rerun SH-G-9 and the service page tests |
| Teardown order: reject, wake, wait, unsubscribe, `close(timeout)`, destroy | Slice 1 step 6 | Rerun BR-G-41 shutdown and XV-18/DR-BR-24 scenarios |
| Pinned Fluent SVG provenance, fixed icon registry, local CSS-mask authority, and icon size ownership | Section 1.9 and GUI Break 1 | Add or change glyphs only with the asset/source/license hash, registry/CSS/package manifest, SH-G-14, and headed gallery evidence in one reviewed change |
| Single-instance `DesktopInstanceIdentity` (`Local\` mutex + activation title), fixed and independent of version and data root | Slice 1 step 7 | Keep the production pair fixed; rerun SH-G-10 (production collision, test coexistence, no override) |
| Database file-pair matrix and coordinated fresh initialization across GUI and CLI | `namisync/interfaces/service.py`, Slice 1 step 8 | Keep the preflight read-only; rerun the pair-state and CLI-composition tests |
| Fluent 2 design language, token source, and the standard M1 window frame | Section 1.9 | Re-transcribe tokens (rerun SH-G-11); a frame change re-runs BR-G-31's native-surface proof |
| Exact GUI-Break-1 13-swatch authored palette, semantic status/operation aliases, and system-color forced-colors override | Section 1.9 and GUI Break 1 | Preserve the current authored values; discuss any added hardcoded or derived color value with the product author first, update this contract and tokens together, and rerun SH-G-11 gallery, contrast, token-ownership, and no-raw-surface-color evidence |
| Whole-window Mica base, opaque content cards (material visible only in chrome/seams), and the high-contrast/no-material fallback | Section 1.9 | Rerun SH-G-12 headed on any pywebview/WebView2/Windows-build change |
| Motion tokens and guardrails (reduced-motion; no virtualized-row animation) | Section 1.10 | Rerun SH-G-13 |

The 256-row visible-window cap and the 256-event history retention cap are
independent constants that happen to share a value. No shared constant may
unify them, and changing one is never a reason to change the other.

## 7. Parallel Delivery Lanes

Serial delivery in section 2's order remains valid. When capacity allows, the
sequence decomposes into the following ownership lanes. Parallel work is
limited to disjoint lane-owned modules; shared bootstrap and harness wiring is
serialized through the current slice integrator.

| Lane | Owns | Contains | Depends on |
| --- | --- | --- | --- |
| **H — Host and transport** | `version.py`, Phase 0/host `pyproject.toml` entries, `launcher.py`, `paths.py`, `logging_config.py`, `host.py`, `bridge.py`, `commands.py`, `slots.py`, `drain.py`, `bridge.js`, harness infrastructure | Phase 0, Slices 1-3, in order | nothing |
| **P — Presentation core and design foundation** | `tokens.css`, `components.css`, `visible_sequence.py`, `tree.js`, `rail.js`, `panels.js`, `app.css` geometry | GUI Break 1 foundation, then Slice 4's pure logic and frame | Stage 5.5 arrays (done); token/component authoring can start at H Slice 1; frame wiring waits for H Slice 1 and headed geometry/gallery waits for H Slice 2 |
| **S — Sync surface** | `plan.js`, plan renderer, overlays, follow mode | Slice 5 | H and P |
| **I — Inventory surface** | `inventory.js`, inventory projections, `view_id` lifecycle, inventory renderer | Slice 6 | H and P; parallel with S |
| **L — Lifecycle and history** | `history.js`, settings UI, `ui-state.json`, close sequencing | Slice 7 | History/settings preparation may follow H and P; final integration and gate closure wait for S and I |
| **R — Release** | PyInstaller spec, lockfile, CI, notices, as-built docs | Slice 8 | everything above |

Phase 0 is not fully parallel: items 1-3 have no semantic dependency and may
land in any order, item 4 follows all three, and item 5 is independent. Edits
to their shared `pyproject.toml` surface still serialize. Each item lands with
its own tests. Lane P's pure `visible_sequence.py` work can start immediately;
its frame integration waits for H's initial assets, and its headed checks wait
for the harness.

Only S ∥ I is a complete vertical parallel pair. Their final layout always uses
the separate `plan.js` and `inventory.js` modules listed in section 1.6; staffing
does not change architecture. `app.js`, `panels.js`, and shared harness
registration are integration files and have one editor after lane-owned modules
and tests are ready. Lane L may prepare disjoint history/settings work earlier,
but Slice 7 integration and closure remain after Slices 5 and 6 as required by
`M1_BRIDGE.md`.

GUI Break 1 splits by lane: its material mechanism is Lane H's, while
`tokens.css`, `components.css`, and the gallery are Lane P's and may begin at
Slice 1, though the break's scheduled close sits before Slice 4. GUI Break 2 is
a whole-surface integration pass with a single editor, after Slices 5-7.

## 8. Atomicity, Idempotency, and Orthogonality Rules

The spec already implies most of these; this section makes them normative so
they are reviewable and testable.

### 8.1 Atomicity

- Every numbered Phase 0 item and slice step is one revertible change landing
  with its tests. A step whose tests cannot land with it is mis-sliced.
- Slice 1 steps 5 and 6 are separate atoms: the startup order and the close
  state machine land as distinct changes even though both live in `host.py`.
  The step 1 rename is behavior-free and lands alone.
- Slice 2's command table, pre-handler refusal layer, `slots.py`, and the
  headed harness are four atoms.
- `settings.json` and `ui-state.json` writes go through write-to-temp and
  atomic replace in the destination directory. BR-G-41's corruption recovery
  remains the read-side guard; replace is the write-side guard, and the GUI
  never half-writes either file.
- Coordinated fresh database initialization (Slice 1 step 8) is atomic in
  effect: a caught partial failure removes only what that attempt created and
  never a pre-existing file, and a crash between the ledger and history
  publications is recovered by the exactly-one-present refusal on the next
  launch.
- GUI Break 1's `tokens.css`/`components.css` foundation lands before any surface
  renderer consumes it; a renderer (Slices 4-7) that introduces its own color or
  control CSS is mis-sliced.

### 8.2 Idempotency

Already required, restated here as one list: logging configuration
(section 1.4); host preparation, which the start wrapper repeats
(`docs/DESKTOP_UI.md`); the synchronous `before_load` installer; serialized
teardown attempts, where only a completed attempt permits the one programmatic
close (Slice 1 step 6); repeated `pywebviewready` handling with at most one
drain per task (section 1.8); and receipted-command retry under one
`command_id`, with a revision only for commands formed against a revisioned
view (section 1.8).

Added by this section:

- `AppPaths` directory creation is create-if-absent and safe to repeat.
- The single-instance mutex is acquired once and held for the host lifetime;
  re-acquisition by the same process is not attempted.
- A second user close gesture during an active teardown is vetoed and leaves
  that attempt in charge; it never joins or blocks on the UI thread. After an
  incomplete attempt, only the explicit Retry Close action starts another
  off-thread `NamiSyncService.close(timeout)` call. The service owns retry
  settlement; the host owns the one-at-a-time UI state.
- History repair reads are idempotent by construction: a repair is a fresh
  traversal, never a mutation of pager state.
- `validate_database_contracts()` is read-only and repeatable: re-running it
  never changes pair state or touches a file.

### 8.3 Orthogonality

One owner per decision; intentional couplings are named.

- `paths.py` owns root resolution and creation; `logging_config.py` consumes
  an `AppPaths` value and composes no path of its own.
- `host.py` owns sequencing; `pywebview_runtime.py` owns pywebview
  primitives; `bridge.py` owns dispatch security. No file duplicates
  another's checks.
- `visible_sequence.py` alone owns windowing and the 256-row cap; `tree.js`
  renders what it is given and re-validates nothing.
- `request_id` (one transport attempt) and `command_id` (one user gesture)
  remain orthogonal identities; neither is derived from the other.
- Single-instance identity is one immutable `DesktopInstanceIdentity` object,
  passed to both the holder and the activator rather than re-derived, and keyed
  to the logon session — never to product version, `AppPaths`, or `--data-dir`.
  Only the headed harness injects an alternate (test) identity, at construction.
- Command allowlisting is constructor-only: `commands.py` owns the production
  mapping, the host passes it, and only the harness composes
  `production + test_report`. No runtime, argv, environment, or bridge
  registration path exists.
- The document CSP has exactly three witnesses — the authored `index.html`,
  `M1_BRIDGE.md`'s normative string, and SH-G-7's expected literal — and no
  fourth: there is no production Python CSP constant, because the HTML is
  authored, not generated.
- `--data-dir` is application-composition input, never session authority.
- `version.py` is the single product/distribution version source with three
  witnesses (SH-G-4). Every schema, protocol, policy, contract, dependency,
  and runtime version remains with its owning layer and is never derived from
  the product version.
- The named constants 28 (`ROW_H`), 256 (visible window), 256 (history
  events), 5 MiB (log budget), and 128/64 (replay/subscriber capacities) are
  independent decisions; no shared constant, helper, or "cleanup" may unify
  any pair.
- `tokens.css` owns color and scale, `components.css` owns control CSS, and
  surface modules consume both and define neither; section 1.9 owns the material
  scope and section 1.10 the motion tokens. The Fluent look has one token
  source, not per-surface palettes.
- One intentional coupling: the read-only .NET Framework probe serves as both
  the pywebview WinForms prerequisite check and the pythonnet runtime check
  (section 1.2). That is a decision, not an accident, and it stays a single
  probe.
