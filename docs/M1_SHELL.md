# M1 Desktop Shell Delivery Plan

Status (2026-08-04, revised 2026-08-06): implementation plan for the remaining
M1 desktop shell. The revision folds in the bounded-history and
terminal-cleanup outcomes recorded in `docs/HANDOFF.md` and adds sections 5-8.
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
8. Give database contract refusal a visible surface. Service construction or
   first dispatch against ledger/history contract markers that mismatch the
   supported versions fails with the documented coordinated manual reset
   direction. The GUI presents that refusal actionably — a native message box
   before window creation or an error document inside the window — and never
   exits silently, because the GUI-subsystem process has no console. Startup
   never migrates or deletes automatically; after refusal every database file
   is byte-identical.

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

The GUI is a recovery consumer, not a continuity consumer, but the normal path
must not lean on recovery: the task observation attaches before execution
admission starts the workflow, so an ordinary run inside the BR-G-42 envelope
sees no `Gap` with the production 128/64 replay/subscriber capacities.
`docs/DISPATCHER.md` still owns the continuity policy; bursts beyond that
envelope remain visible, replay-recoverable churn through the
`Gap`/resubscribe path rather than a reason to invent replay headroom.

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

History paging follows the bounded readback contract exactly. A fresh event
traversal whose live cursor is ahead of durability returns the empty terminal
page — durable `through_seq`, unchanged `next_after_seq`, `has_more=False` —
and `history.js` treats that page as the end of that traversal, not a
retryable error. A later repair issues a fresh read that omits `through_seq`
and captures the new committed prefix; an explicit reversed fixed interval
remains invalid.

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
  per-user directory untouched, proven by probing that directory rather than
  by trust; a relative `--data-dir` is refused before any directory is
  created. A static scan proves no module other than `paths.py` reads
  `LOCALAPPDATA` or composes the product directory name. *Not satisfied by*
  unit-testing the resolver while another component builds its own path.
- **SH-G-3 — Logging is proven by emitted records.** Configuring twice yields
  one handler set; a real child GUI-path process shows pywebview records in
  the file and nothing on the console; rotation is exercised across the 5 MiB
  boundary; injected thread-level and process-level exceptions both appear;
  and a dispatched hostile command leaves no raw body or filesystem path in
  the emitted file. *Not satisfied by* asserting handler configuration
  without records or by logging only from the test process.
- **SH-G-4 — One version, three witnesses.** `namisync.version.VERSION`,
  installed distribution metadata, and the startup log record agree, with the
  metadata read from the installed distribution. *Not satisfied by* comparing
  the constant to itself.
- **SH-G-5 — Database contract refusal has a visible GUI surface.**
  Fault-injecting mismatched ledger/history contract markers into an isolated
  root produces the documented coordinated-manual-reset direction on a
  visible GUI surface, leaves every database file byte-identical, and does
  not exit silently. *Not satisfied by* a log-only refusal or by testing the
  service exception without the GUI surface.
- **SH-G-6 — The wheel is the artifact under test.** The built wheel contains
  every packaged asset, `importlib.resources` resolves `index.html` from the
  installed wheel in a clean venv, and the headed smoke scenario loads that
  resolved page. *Not satisfied by* resolving from the source tree.
- **SH-G-7 — Static frontend invariants scan the shipped file set.** Over the
  exact asset set the wheel ships: `window.pywebview` appears only in
  `bridge.js`; the CSP meta element is the first element of `head`; no inline
  script or event attribute exists; and the CSS/JS row-height declarations
  are integer-equal, with the headed hostile-row measurement matching
  `ROW_H`. *Not satisfied by* scanning a hand-maintained file list that is
  not derived from the packaged asset set.
- **SH-G-8 — The drain attaches before work starts.** A test proves the task
  observation is subscribed before execution admission starts the workflow,
  and no `Gap` occurs inside the BR-G-42 normal envelope; a fault-injected
  burst beyond that envelope recovers through the existing `Gap`/resubscribe
  path. *Not satisfied by* attaching after start and relying on replay.
- **SH-G-9 — The history pager terminates on the empty terminal page.** A
  fault-injected traversal whose live cursor is ahead of durability renders
  the committed prefix and stops on the empty terminal page; a later repair
  captures the new committed prefix through a fresh read that omits
  `through_seq`; a request counter proves no retry loop. *Not satisfied by*
  treating the empty terminal page as an error or by testing only a fully
  durable run.
- **SH-G-10 — The gate ledger is executable.** A meta-test reads the closed
  BR-G and SH-G ids for every slice this file marks complete and fails when a
  collected test named for one of them is missing or deselected; the release
  command collects every such test. *Not satisfied by* a checklist, a marker
  file, or a skipped test.

The concrete homes: `tests/interfaces/test_launcher.py` (SH-G-1),
`tests/interfaces/web/test_paths.py` (SH-G-2),
`tests/interfaces/web/test_logging_config.py` (SH-G-3),
`tests/test_version.py` (SH-G-4), `tests/interfaces/web/test_startup_refusal.py`
(SH-G-5), `tests/interfaces/web/test_wheel_assets.py` (SH-G-6),
`tests/interfaces/web/test_frontend_static.py` (SH-G-7),
`tests/interfaces/web/test_drain.py` (SH-G-8),
`tests/interfaces/web/test_history_pager.py` (SH-G-9), and
`tests/test_gate_ledger.py` (SH-G-10). A gate test may live elsewhere only if
the ledger meta-test still finds it by name.

## 6. Contract and Policy Watchlist

Each row names a policy that must not drift silently, the authority that owns
it, and the action any change requires. "Rerun" means the named gates run
against the changed configuration before the change lands.

| Policy | Authority | On change |
| --- | --- | --- |
| 256-event/1-MiB/one-second history window policy | `docs/HISTORY.md`, reaffirmed in `docs/HANDOFF.md` | Rerun the documented 50-run/1,000,000-item benchmark and all its gates |
| 128/64 replay/subscriber capacities; no invented replay headroom | `docs/DISPATCHER.md` | UI/load evidence or a readiness-handshake design, never a constant bump |
| `pywebview==6.2.1`, `pythonnet==3.1.0`, `clr_loader`, Bottle floor, return transport | Section 1.2 | Rerun the native reality and hostile-text gates (BR-G-30/31/32 family) |
| Windows `netfx` runtime path and `PYTHONNET_RUNTIME` conflict refusal | `docs/DESKTOP_UI.md` | Re-probe and update the shared prerequisite check |
| CSP, exact-origin, and navigation/popup guards | `docs/M1_BRIDGE.md` | Rerun BR-G-31/BR-G-32 headed scenarios |
| `private_mode=True` with explicit `storage_path` | Section 1.3 | Headed retest of the storage branch on any pywebview upgrade |
| `BridgeDispatcher` exposes only `dispatch` | Section 1.8 | Underscore the new member and keep the static test passing |
| Two-declaration `ROW_H` equality | Section 1.7 | Keep the parse test and headed measurement passing |
| Import-linter layers including `launcher` | `pyproject.toml` | `lint-imports` stays in the release command |
| Reliable readback semantics: sparse inclusive `through_seq`, empty terminal page | `interfaces/service.py`, `docs/HISTORY.md` | Rerun SH-G-9 and the service page tests |
| Teardown order: reject, wake, wait, unsubscribe, `close(timeout)`, destroy | Slice 1 step 6 | Rerun BR-G-41 shutdown and XV-18/DR-BR-24 scenarios |

The 256-row visible-window cap and the 256-event history retention cap are
independent constants that happen to share a value. No shared constant may
unify them, and changing one is never a reason to change the other.

## 7. Parallel Delivery Lanes

Serial delivery in section 2's order remains valid. When capacity allows, the
sequence decomposes into lanes that share no production files, the same way
`M1_BRIDGE.md` decomposed Stage 5.5:

| Lane | Owns | Contains | Depends on |
| --- | --- | --- | --- |
| **H — Host and transport** | `launcher.py`, `paths.py`, `logging_config.py`, `host.py`, `bridge.py`, `commands.py`, `slots.py`, `drain.py`, `bridge.js`, harness assets | Phase 0, Slices 1-3, in order | nothing |
| **P — Presentation core** | `visible_sequence.py`, `tree.js`, `rail.js`, `panels.js`, `app.css` geometry | Slice 4's pure logic and frame | Stage 5.5 arrays (done); its headed geometry check waits for Lane H's Slice 2 harness |
| **S — Sync surface** | plan renderer, overlays, follow mode | Slice 5 | H and P |
| **I — Inventory surface** | inventory projections, `view_id` lifecycle, inventory renderer | Slice 6 | H and P; parallel with S |
| **L — Lifecycle and history** | `history.js`, settings UI, `ui-state.json`, close sequencing | Slice 7 | H (Slices 2-3) and P's frame; parallel with S and I |
| **R — Release** | PyInstaller spec, lockfile, CI, notices, as-built docs | Slice 8 | everything above |

Phase 0's six items are mutually independent and may land in any order. Lane P
can start immediately: `visible_sequence.py` is pure over workflow-owned
arrays, and the JavaScript modules are authorable and unit-testable before a
window exists; only their headed checks queue behind the harness.

Two boundary rules make S ∥ I ∥ L safe. First, no two lanes edit one file.
After Slice 4 lands, the frame skeleton belongs to Lane P; if S and I run
concurrently, plan- and inventory-specific panel rendering split into
`plan.js` and `inventory.js`, and rail task-lifecycle presentation passes to
Lane L, amending section 1.6's target layout accordingly. Serial delivery may
keep the smaller listed set. Second, each surface adds its own hostile-text
headed scenario to the shared harness rather than editing another lane's
scenario.

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

### 8.2 Idempotency

Already required, restated here as one list: logging configuration
(section 1.4); host preparation, which the start wrapper repeats
(`docs/DESKTOP_UI.md`); the synchronous `before_load` installer; teardown,
which runs once while the later programmatic close passes through
(Slice 1 step 6); repeated `pywebviewready` handling with at most one drain
per task (section 1.8); and mutation retry under one `command_id`
(section 1.8).

Added by this section:

- `AppPaths` directory creation is create-if-absent and safe to repeat.
- The single-instance mutex is acquired once and held for the host lifetime;
  re-acquisition by the same process is not attempted.
- A second user close gesture during visible closing joins the in-flight
  teardown. `NamiSyncService.close(timeout)` already returns its settled
  `ShutdownView` on repeat calls; the host relies on that rather than
  guarding it again.
- History repair reads are idempotent by construction: a repair is a fresh
  traversal, never a mutation of pager state.

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
- `--data-dir` is application-composition input, never session authority.
- `version.py` is the single version source with three witnesses (SH-G-4).
- The named constants 28 (`ROW_H`), 256 (visible window), 256 (history
  events), 5 MiB (log budget), and 128/64 (replay/subscriber capacities) are
  independent decisions; no shared constant, helper, or "cleanup" may unify
  any pair.
- One intentional coupling: the read-only .NET Framework probe serves as both
  the pywebview WinForms prerequisite check and the pythonnet runtime check
  (section 1.2). That is a decision, not an accident, and it stays a single
  probe.
