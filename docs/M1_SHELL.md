# M1 Desktop Shell Delivery Plan

Status (2026-08-04): implementation plan for the remaining M1 desktop shell.
Stages 1-5.5 and the WebView2 reality spike are complete; no product window or
packaged frontend has shipped. NamiSync remains version `0.1.0` until M1 is
complete. Finishing M1 makes the product beta-ready; any later version change
is a separate release decision.

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
path; it is never browser-supplied and never persisted as session authority. A
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
standard-library-only and writes UTF-8 rotating files under
`%LOCALAPPDATA%\NamiSync\logs` (or the injected isolated root). The initial
budget is one 5 MiB active file plus five backups.

The same handler is attached to the `namisync` and `pywebview` loggers before
pywebview import. This prevents pywebview 6.2.1 from adding its default console
handler and retains swallowed event-handler and native-host failures. Records
include UTC time, process, thread, level, and logger. Startup records the
NamiSync, Python, OS, pywebview, pythonnet, `clr_loader`, Bottle, and observed
WebView2 versions. Process- and thread-level unhandled exceptions are retained.
Raw bridge command bodies and returned filesystem data are not logged.

Logging configuration is idempotent. Failure to create the application data
or log directory is an actionable pre-window startup failure rather than a
silent no-logging mode. Normal exit calls `logging.shutdown()` after the GUI
loop ends.

### 1.5 Product version and license metadata

`namisync/version.py` contains the single `VERSION` constant. Setuptools reads
it through `[project] dynamic = ["version"]` and
`[tool.setuptools.dynamic] version = {attr = "namisync.version.VERSION"}`.
Runtime/About/logging expose the same value, and a test compares it with
installed distribution metadata. The value stays `0.1.0` throughout M1; this
plan does not preselect the next version or a suffix.

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
    commands.py
    drain.py
    slots.py
    visible_sequence.py
    assets/
        index.html
        app.css
        app.js
        bridge.js
        tree.js
        rail.js
        panels.js
        history.js
namisync/interfaces/launcher.py
tests/assets/
    headed_harness.html
    headed_harness.js
```

`visible_sequence.py` owns tree-agnostic flatten/window/search/filter/anchor
presentation. `tree.js` virtualizes and renders windows already decided by the
server; it never reconstructs hierarchy or filters an already-windowed page.

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
mutating user gesture and survives uncertain delivery and retry. Read-only
requests may retry with a new request id; mutations retry with a new request id
and the same command id and revision. Drains recover from the last sequence the
client accepted rather than using a mutation receipt. Repeated
`pywebviewready` events install no duplicate listeners and rearm at most one
drain per task.

The Python `BridgeDispatcher` instance exposes only `dispatch`; every other
instance member remains underscore-prefixed because pywebview recursively
walks and reads public attributes during injection.

## 2. Delivery Sequence

### Phase 0 - Before the product shell

Phase 0 contains host-shaping prerequisites and small packaging corrections.
It creates no WebView window.

1. Add the single runtime version source and retarget project metadata to it;
   keep `0.1.0`.
2. Add GUI `AppPaths` resolution and an injectable isolated data root.
3. Add bounded file logging and pywebview logger capture, with configuration
   callable before pywebview import.
4. Declare the exact pythonnet dependency and Bottle floor; document and guard
   the tested Windows `netfx` runtime.
5. Declare `LICENSE` through `license-files`.
6. Add focused tests for version agreement, path resolution/isolation, log
   rotation/idempotence, pywebview logger capture, dependency declarations,
   and the guarantee that logging/path setup imports no `webview` module.

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
   configure paths and logging
   prepare_pywebview_host(webview)
   create pending NativeDocumentState
   create BridgeDispatcher(document=pending_state)
   create_window(local index path, js_api=dispatcher)
   start_edge_chromium(http_server=True, private_mode=True,
                       storage_path=paths.webview2)
       initialized -> renderer check
                   -> ExactOrigin.from_url(window.real_url)
                   -> bind pending document origin exactly once
                   -> register synchronous before_load installer
       before_load -> UI thread -> attach native guards
       loaded      -> verify attached/no attachment_error
   ```

   Dispatch remains closed while document authority is pending or failed.
   Pywebview private window fields are not mutated to solve construction order.
6. Implement the host close state machine now: user close is vetoed on the UI
   thread, closing becomes visible, teardown runs once off-thread, and the later
   programmatic close is allowed through without recursively starting teardown.
   The eventual teardown order is reject new dispatches, wake drains and
   capacity waiters, wait for admitted handlers, unsubscribe task observations,
   call `NamiSyncService.close(timeout)`, and destroy only when the returned
   shutdown view is complete. The service call retains its existing internal
   order: `SessionObserver.close()` closes streams and joins observers before
   dispatcher/runtime closure. The host does not reach into the service to
   close that observer twice. Slice 1 supplies empty wake/subscription hooks for
   later slices rather than blocking the UI thread.
7. Add a per-interactive-session named mutex retained for the host lifetime.
   A second launch finds the exact product window title, restores it, attempts
   `SetForegroundWindow`, reports activation failure visibly, and exits zero.
   No IPC or `AllowSetForegroundWindow` protocol is introduced.

Slice 1 closes the revised BR-G-19 and BR-G-31 host clauses. It proves wheel
installation, not yet the final PyInstaller artifact.

### Slice 2 - Command transport, slots, and headed harness

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
   and render functions. Test-only report handlers are injected only into the
   harness and are asserted absent from production commands and build output.
5. Each headed scenario runs in a child process with a hard parent timeout.
   JavaScript reports observed values through `dispatch("test_report")`; Python
   performs the assertion and destroys the window. NamiSync test code uses no
   `evaluate_js`.
6. The BR-G-32 hostile-text scenario takes its corpus from Python, crosses
   pywebview's `js_bridge_call` interpolation and `JSON.parse`, renders through
   the production `textContent` path, reads `.textContent` back in JavaScript,
   and returns it through `test_report`. Python asserts byte-for-byte equality.

Slice 2 closes the transport portion of BR-G-32. The production plan and
inventory DOM portions close only with slices 5 and 6.

### Slice 3 - Event drain

Implement `drain.py`: bounded queue, replaceable progress coalescing, reliable
backpressure, one server-enforced drain per task, bounded long-poll wait,
sequence-gap recovery, terminal-record reconciliation, and shutdown wakeups.
Fault-inject lost reliable and terminal responses and repeat
`pywebviewready` while a drain is outstanding. This closes BR-G-33 and retains
XV-18 shutdown behavior.

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
task close sequencing, shutdown retry/incomplete presentation, and normal
single-instance activation behavior. Close BR-G-40, BR-G-41, and the history
portion of BR-G-42.

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
release command then collects every BR-G gate:

```powershell
# Ordinary development suite
.\.venv\Scripts\python.exe -m pytest -q

# Real WebView2 scenarios
.\.venv\Scripts\python.exe -m pytest -q -o "addopts=" -m headed tests\interfaces\web

# Release suite: include headed and ordinary tests
.\.venv\Scripts\python.exe -m pytest -q -o "addopts="
.\.venv\Scripts\lint-imports.exe
git diff --check
```

On the supported Windows profile, missing WebView2 fails headed verification
actionably; it is not a skip or xfail. Every `test_br_g_*` test is collected by
the release command.

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
