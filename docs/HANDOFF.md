# NamiSync Session Handoff

Date: 2026-07-30
Branch: `milestone1`

## Session Outcome

Completed the M1 Stage 6 slice-0 pywebview reality spike on top of the landed
integrated M1 audit.

- Pinned the measured host dependency as `pywebview==6.2.1`; the editable
  distribution metadata now declares it alongside `xxhash`.
- Replaced worker-thread `CoreWebView2` access with one idempotent installer
  registered on pywebview's synchronous `before_load` event. The installer
  verifies WinForms UI-thread ownership and attaches `NavigationStarting`,
  `NewWindowRequested`, and `SourceChanged` before application calls are
  exposed.
- Replaced `window.get_current_url()` dispatch authority with
  `NativeDocumentState`, a lock-protected snapshot updated from native
  `CoreWebView2.Source`. Dispatch remains fail-closed before attachment and
  after a genuinely off-origin native source, but a rejected navigation target
  cannot lock the still-trusted packaged page out of the bridge.
- Added permanent regressions for deferred/idempotent UI-thread attachment,
  off-UI refusal, fail-closed pre-attachment behavior, canceled-navigation
  continuity, and committed off-origin rejection.
- Updated the bug log, interface/desktop/architecture contracts, M1 plan and
  bridge gates, README dependency guidance, and changelog.

No facade, workflow, dispatcher, core, module, database, schema, migration, or
CLI contract changed. The headed product window, packaged assets, event drain,
and launcher remain later Stage 6 slices.

## Live Reality Evidence

The live Windows run used CPython 3.13.14 x64, pywebview 6.2.1,
pythonnet 3.1.0, and Microsoft Edge WebView2 Runtime 150.0.4078.105.

- Forced `gui="edgechromium"` selected the Edge Chromium renderer.
- The packaged static asset received a random loopback origin; the final
  verification run used `http://127.0.0.1:7016`.
- `Microsoft.Web.WebView2.Core.CoreWebView2` was reachable and pythonnet native
  event `+=`/`-=` syntax worked on the WinForms UI thread.
- Direct `CoreWebView2` access from pywebview's setup worker deadlocked in the
  original probe. The revised `initialized -> before_load` path attached
  without deadlock.
- After native cancellation of `https://example.invalid/`,
  `window.get_current_url()` still reported that rejected URL, but the native
  source remained trusted and the packaged page's `after-cancel` dispatch
  succeeded through `NativeDocumentState`.

The run also reconfirmed a separate Stage 6 transport constraint: canceled
navigation can make pywebview reinject its JavaScript bridge and lose an
in-flight return callback after Python has executed the handler. This slice
does not add transport retries. Slice 2 must preserve command-id receipts for
mutations, and slice 3 must preserve the planned drain resubscription and
terminal-record recovery.

## Verification

- Focused security spike: `10 passed in 0.04s`.
- Full repository: `816 passed in 25.58s`.
- Import boundaries: 49 files / 181 dependencies; all eight contracts kept,
  zero broken.
- Hidden real-WebView2 verification: forced Edge Chromium, attached through
  the production callback path, canceled off-origin navigation, and accepted
  the subsequent trusted-page dispatch.
- Package health: `pip check` reported no broken requirements; installed
  metadata lists `pywebview==6.2.1` and `xxhash<4,>=3.8.1`.
- Explicit CLI import remained headless and did not import `webview`.
- `git diff --check` was clean apart from expected LF-to-CRLF notices.

## Immediate Next Context

Stage 6 slice 1 should preserve this initialization order:

1. Create the window with a JavaScript API object whose only public method is
   `dispatch`; keep every host reference private because pywebview recursively
   exposes public API-object attributes.
2. Before startup, register `window.events.initialized`. When it fires,
   derive the exact random asset origin from `window.real_url`, call
   `configure_pywebview2_security`, and install the resulting document state
   into `BridgeDispatcher`.
3. Let the synchronous UI-thread `before_load` callback attach native handlers
   before pywebview injects the application API.
4. Start only through forced Edge Chromium and surface WebView2 absence
   actionably.

Do not reach `CoreWebView2` from setup or dispatch workers, and do not restore
`get_current_url()` as dispatch authority. The pre-existing executor
operation-safe-pause and audit-timeout parity decisions remain open in
`BUGS.md`; this slice does not change them.
