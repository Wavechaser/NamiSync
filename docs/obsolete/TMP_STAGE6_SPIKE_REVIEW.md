# Stage 6 Spike Review and Shell Checklist

Status: **archived review evidence.** Not an active contract. Created
2026-07-31 to review the Stage 6 slice-0 spike and retained here after every
finding was implemented or promoted. Active documentation governs if it later
diverges from this audit record.

Disposition:

- Findings 1, 2, 5, 6a, and 6b were fixed in the spike code and regressions
  and reflected in active host, UI, architecture, bug, and release docs.
- Findings 3, 4, and 6c were promoted into the active bridge posture,
  real-browser proof, repeatable-readiness/drain recovery, and mutation-retry
  contracts.
- Part 2's normative host/transport/frontend points were folded into the
  applicable active Stage 6 contracts where they sharpened an existing gate.
  The remaining implementation evidence and future shell checklist are
  preserved below as historical audit provenance.

Scope of the review: `namisync/interfaces/web/security_spike.py`,
`tests/test_web_security_spike.py`, and the doc changes in the same working
tree, verified against the vendored pywebview 6.2.1 source in
`.venv/Lib/site-packages/webview/`.

---

## Part 1 — the two fixes in the uncommitted diff

### Fix A — UI-thread affinity via `before_load`: correct

Confirmed against vendor source rather than the spike log alone.

- `webview/window.py:165` — `self.events.before_load = Event(self, True)`.
  `should_lock=True` makes `Event.set()` call handlers inline on the caller's
  thread (`webview/event.py:54-55`), not on a spawned thread. `before_load` is
  genuinely synchronous.
- `webview/util.py:240` — `before_load.set()` fires from `inject_pywebview`,
  called at `webview/platforms/edgechromium.py:389` inside
  `on_navigation_completed`. That is a WebView2 event handler, i.e. the
  WinForms UI thread.
- Firing order is correct: `before_load.set()` at util.py:240 precedes the JS
  API injection thread started at util.py:243. Handlers attach strictly before
  `window.pywebview` exists.
- `window.native.browser.webview` resolves. `native` is the `BrowserForm`
  (`winforms.py:195`), `form.browser` is `EdgeChrome` (`winforms.py:280`),
  `.webview` is the `WebView2` control. `Form.InvokeRequired` is valid.
- The zero-argument `attach_before_load` is called correctly:
  `webview/event.py:40-41` special-cases zero-parameter handlers.

The idempotency guard is necessary rather than merely defensive:
`inject_pywebview` runs on every `NavigationCompleted`, so `before_load` fires
repeatedly for the life of the window.

### Fix B — `NativeDocumentState`: correct, with the exact mechanism

The spike recorded the symptom. The cause:

- `get_current_url()` → `winforms.py:947` returns `browser.url`.
- `browser.url` is assigned at `edgechromium.py:386-387` in
  `on_navigation_completed`: `self.url = str(sender.Source)`. `sender` is the
  **managed** `WebView2` control, whose `Source` tracks navigation *intent* and
  is set the moment navigation begins.
- `NavigationCompleted` fires even when `NavigationStarting` canceled the
  navigation, so pywebview overwrites `browser.url` with the rejected target.

`CoreWebView2.Source` advances only via `SourceChanged`, which WebView2 raises
after a navigation commits and never for a canceled one. The
`SourceChanged`-fed snapshot is therefore the correct authority, and
"a canceled target does not poison the snapshot" is a property of WebView2's
event contract, not incidental behavior.

Attach-time seeding order in `security_spike.py:107-115` is also correct:
subscribe all three events first, then read `Source`. Both run on the UI
thread, so no event can be missed between subscribe and seed.

---

## Findings

### 1. HIGH — pywebview swallows the attachment failure

`webview/event.py:48-49`:

```python
except Exception as e:
    logger.exception(e)
```

Every `RuntimeError` raised inside `attach_before_load` is logged and
discarded. In production, if `CoreWebView2` is `None`, `InvokeRequired` is
true, or the native events are missing, the app opens a window with **no
navigation guards** and a permanently empty document snapshot. Dispatch then
fails closed with `BridgeOriginError` on every call — correct security posture,
but the user gets a blank, silently dead UI and no message.

`test_native_installation_refuses_an_off_ui_before_load_callback` passes only
because the test's `BeforeLoadHook.emit` re-raises. Real pywebview does not.
The test asserts a behavior the system does not have.

**Action.** Make attachment failure observable, not merely raised.

- Record the failure on `NativeDocumentState` (e.g. `attachment_error`).
- `require_trusted()` names the attachment failure in its message.
- Slice 1's host checks the attachment state after `loaded` (or on a short
  deadline) and tears down with an actionable dialog.
- Change `BeforeLoadHook.emit` in the test to swallow-and-record like the real
  `Event.set`, and assert the failure is *visible*, not that it propagates.

### 2. HIGH — pywebview opens attacker-chosen URLs in the user's real browser, before our handler runs

`webview/platforms/edgechromium.py:255-261`:

```python
def on_new_window_request(self, sender, args):
    args.set_Handled(True)
    if webview_settings['OPEN_EXTERNAL_LINKS_IN_BROWSER']:
        webbrowser.open(str(args.get_Uri()))
    else:
        self.load_url(str(args.get_Uri()))
```

`OPEN_EXTERNAL_LINKS_IN_BROWSER` defaults to `True`
(`webview/__init__.py:125`). pywebview subscribes this handler at
`CoreWebView2InitializationCompleted` (`edgechromium.py:276`), strictly before
our `before_load` attachment. .NET invokes handlers in subscription order, so
pywebview wins and launches the system browser. Our `Handled = True` runs
afterward and cannot undo it.

`window.open('https://evil/')` from the renderer therefore escapes the sandbox
into the user's default browser today.
`test_native_webview2_hooks_cancel_untrusted_navigation_and_all_popups` cannot
observe this because `FakeCoreWebView2` has no pre-registered pywebview
handler.

**Action.** Before `create_window`:

```python
webview.settings['OPEN_EXTERNAL_LINKS_IN_BROWSER'] = False
webview.settings['ALLOW_FILE_URLS'] = False   # default True; adds
                                              # --allow-file-access-from-files
```

`webview.settings` is an `ImmutableDict` (`webview/util.py:48-64`): existing
keys are assignable, new keys are not. With the flag off, pywebview falls back
to `load_url(uri)` on the main window, which `NavigationStarting` cancels.

Stronger option: in `attach()`, remove pywebview's handler before adding ours —
`core.NewWindowRequested -= window.native.browser.on_new_window_request`. The
spike proved `-=` works through pythonnet, but this case is a **bound method**
delegate, which pythonnet handles least predictably; verify it specifically
before relying on it.

**Test shape.** Give `FakeCoreWebView2` a pre-registered foreign handler with an
observable side effect and assert either that attachment removes it or that the
settings are hardened.

### 3. HIGH — "no `evaluate_js` for application data" is false at the system level

`webview/util.py:255-266` is how every `dispatch` return value reaches JS:

```python
result = json.dumps(result).replace('\\', '\\\\').replace("'", "\\'")
retval = f"{{value: '{result}'}}"
...
window.evaluate_js(
    f'window.pywebview._returnValuesCallbacks["{func_name}"]["{value_id}"]({retval})'
)
```

with `resolve(JSON.parse(value))` on the JS side (`webview/js/api.js:151`).
Every hostile filename returned from `dispatch` passes through pywebview's
hand-rolled escaper into JavaScript **source text** — exactly the pattern
DR-M1-15 §1 forbids in our own code.

It appears safe, but only because `json.dumps` defaults to `ensure_ascii=True`.
Every non-ASCII character, including U+2028 and U+2029 (which terminate a JS
string literal), is emitted as a six-character ASCII backslash-u escape before
the backslash-doubling pass. That is load-bearing third-party escaping.

**Actions.**

- The `pywebview==6.2.1` pin now does security work. Any version bump must
  re-audit `util.js_bridge_call`. State this in `INTERFACES.md`.
- Restate the invariant honestly in `INTERFACES.md` and `M1_PLAN.md` §5:
  *NamiSync code* never constructs JavaScript; the pinned host's return
  transport does, and is covered by a real-browser test.
- XV-19 / BR-G-30's current proof
  (`test_bridge_source_has_no_host_to_javascript_application_data_channel`)
  greps our own module and structurally cannot see this. Upgrade DR-BR-25's
  real-browser hostile-name test into a full round trip: dispatch from real JS
  → real pywebview transport → `textContent` render → read the rendered text
  back and compare bytes.

Not an escalation, but worth recording: `func_name` and `value_id` in that
f-string originate from the page's own web message (`edgechromium.py:244-251`).
A compromised renderer can execute JS in itself, which it could already do.

### 4. MEDIUM — the re-injection loop is unconditional on navigation success

`edgechromium.py:385-389` calls `inject_pywebview` on every
`NavigationCompleted`, including failed and canceled ones. Each call re-runs
`before_load`, re-injects `api.js`, and rebuilds
`window.pywebview._returnValuesCallbacks` from scratch, dropping every in-flight
promise. The handoff notes the symptom; the detail to record is that it is
**unbounded and page-triggerable** — any navigation attempt, even one our guard
cancels, resets the bridge.

This is the correct justification for slice 2's command-id receipts and slice
3's drain resubscription. One addition: the JS side must treat `pywebviewready`
(`webview/js/finish.js:6`) as a **repeatable** event, keep init idempotent, and
re-establish the outstanding `next_events` request each time it fires.

### 5. MEDIUM — only top-level navigation is guarded

`CoreWebView2.NavigationStarting` does not fire for iframe navigations; those
are `FrameNavigationStarting` / `CoreWebView2Frame`. Frames are currently
covered only by the CSP's `frame-src 'none'` — a single document-level control,
which is the same "one control is not defense in depth" argument DR-M1-15 makes
about the inbound half.

**Action.** Either hook `FrameNavigationStarting`, or write down explicitly in
`DESKTOP_UI.md` that frames are a CSP-only control, and add a test asserting the
CSP string contains `frame-src 'none'`.

### 6. LOW — three smaller items

- **Over-broad exception mapping.** `start_edge_chromium` maps any
  `WebViewException` to "install WebView2". pywebview raises that type for
  unrelated conditions (duplicate window UID, "GUI is not initialized" at
  `webview/window.py:47`). Match on the message, or import the concrete type
  lazily inside the `except`.
- **Origin derivation trap.** `ExactOrigin.parse` rejects any path other than
  `""`/`"/"`, but `window.real_url` is `http://127.0.0.1:7016/index.html`.
  Slice 1 must strip it with `urlsplit` + reconstruct, **not**
  `rsplit("/", 1)` as the test helper does: `rsplit` yields `http:/` for a bare
  origin and breaks on a query string.
- **Dispatch-time TOCTOU.** `require_trusted()` runs once at entry, then the
  handler runs for an arbitrary time on a worker thread; the document can change
  mid-handler. Exposure is small because off-origin navigation is canceled, but
  DR-BR-27 should state whether a completed-but-undelivered mutation is
  retryable.

---

## Part 2 — remaining work for the full Stage 6 shell

`M1_BRIDGE.md` §10 already owns the slice table and the 44 BR-G gates. This
section records only what the reality spike changed or newly exposed, plus the
frontend material.

### Host (slice 1)

**Hardening block before `create_window`,** beyond the two settings in finding
2:

```python
webview.settings['OPEN_EXTERNAL_LINKS_IN_BROWSER'] = False
webview.settings['ALLOW_FILE_URLS'] = False
webview.settings['ALLOW_DOWNLOADS'] = False       # already default; pin it
webview.settings['REMOTE_DEBUGGING_PORT'] = None  # already default; pin it
```

**`debug=False` is security-relevant, not cosmetic.**
`edgechromium.py:287-294` ties `AreDevToolsEnabled`,
`AreBrowserAcceleratorKeysEnabled`, `AreDefaultContextMenusEnabled`, and
`IsStatusBarEnabled` directly to the debug flag. A packaged build must assert
it is false.

**`initialized` handler signature footgun.** `webview/event.py:40-45`: a
zero-parameter handler is called with no arguments; a handler with a parameter
*named* `window` is called as `func(window, renderer)`; any other
single-parameter handler receives `func(renderer)`. Use zero parameters, close
over what is needed, and comment why.

**`window.events.closing` is the DR-BR-22 hook and it can veto.** `Event.set()`
returns `True` when any handler returned `False` (`webview/event.py:60-63`), and
winforms uses that to cancel the close (`winforms.py:400-401`). `closing` is
`should_lock=True`, so it runs synchronously on the UI thread — "cancel busy
tasks, wait for terminal records, then close" must not block there. Return
`False` immediately, run teardown asynchronously, then close the window
programmatically when it completes.

**Ordered shutdown is an unbuilt named gate.** XV-18 requires: close every
`EventStream`, join observer threads, wake the outstanding `next_events` drain,
shut down the dispatcher, close the runtime — in that order, under a bounded
deadline. Highest-likelihood source of "app will not exit", because DR-M1-19's
deliberate no-timeout blocking `next()` hangs forever without it.

**Single instance.** The named cross-process mutex from DR-M1-04 is the same
primitive. The hard half is activation: `SetForegroundWindow` from a second
process is blocked by Windows unless the target calls
`AllowSetForegroundWindow` or the caller owns the foreground. BR-G-31 already
requires that activation failure be visible and non-error.

**Packaged assets.** Decide how `index.html` is located from source and when
frozen (`importlib.resources` vs `sys._MEIPASS`); pywebview ships a PyInstaller
hook at `webview/__pyinstaller`. The asset server is real HTTP on loopback
(bottle, `webview/http.py:151`), so any local process can fetch the static
assets — harmless, but the packaged directory must contain assets only.

### Frontend

**What the frontend is.** Three files — `index.html`, `app.css`, `app.js` —
served over loopback HTTP into an embedded Chromium.

**Recommendation: no framework, no build step.** WebView2 is current Chromium,
so plain ES modules (`<script type="module" src="app.js">`) give imports and
modern syntax with zero toolchain. A bundler would add a Node dependency to a
Python product, reopen the `script-src` argument, and put a
minification/source-map layer between the audit and the shipped code. It would
also weaken XV-19's `innerHTML` grep, which is only meaningful over hand-written
source. The UI is a rail, a tree, and panels; vanilla DOM is the right tool.

**CSP must be a `<meta>` tag, not a header** — pywebview's static server adds no
headers. It must be the first element in `<head>`; anything before it is
uncovered.

```html
<meta http-equiv="Content-Security-Policy"
      content="default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'">
```

Two supporting facts: `'self'` resolves to the loopback origin the asset server
picked, so the random port needs no special handling; and WebView2's
`ExecuteScriptAsync` — how pywebview injects `api.js` — is not subject to page
CSP, so `script-src 'self'` does not break the bridge.

**XSS sinks.** `el.textContent = name` sets text; the browser never parses it as
markup. `el.innerHTML = name` parses it as HTML and is how a filename becomes
code. `innerHTML` is not the only sink, and a single-token grep will miss:

- `insertAdjacentHTML`, `outerHTML`, `document.write`
- `el.setAttribute('href' | 'src', v)` — never build a URL from filesystem data
- `el.style.cssText = v` and `style` attributes built from data
- `eval`, `new Function`, `setTimeout("string")`, `setInterval("string")`

Write the XV-19 grep as an allowlist covering all of these.

**Virtualized rendering for 120k nodes.** Do not create 120k DOM elements. The
backend already windows to 256 rows (DR-BR-15/16); the frontend mirrors it: a
scroll container, an absolutely-positioned spacer sized
`totalRows * rowHeight` so the scrollbar is honest, and only the visible slice
plus roughly ten rows of overscan in the DOM. On scroll,
`firstVisible = Math.floor(scrollTop / rowHeight)` selects the window to
request. **Use a fixed row height** — variable heights turn arithmetic into a
measurement cache that is not needed here.

**Event delegation.** One `click` listener on the tree container reading
`event.target.closest('[data-node-id]')`, not one per row. Virtualized rows are
created and destroyed constantly; per-row listeners leak and cost.

**Bridge mental model.** `window.pywebview.api.dispatch(json)` returns a
Promise. It does not exist at page load: gate everything on
`window.addEventListener('pywebviewready', ...)`, and per finding 4 that event
can fire more than once, so init must be idempotent and must re-arm the event
drain each time.

### Transport (slices 2–3)

`webview/util.py:336` spawns **a new unbounded thread per exposed-function
call**. Two consequences:

- DR-BR-24's "bridge handlers are concurrent and must be synchronized" is now
  empirically confirmed, not assumed.
- A blocking `next_events` long-poll occupies one such thread for its whole
  duration. Bound the wait (25–30 s), return empty, and let the client re-ask
  immediately. It must also be woken on window close or shutdown hangs.

pywebview catches handler exceptions and rejects the JS promise with
`{message, name, stack}` (`webview/util.py:258-262`) — a full Python traceback
reaches the renderer. Low severity since the page is ours, but keep
`BridgeProtocolError` messages free of paths and internals.

---

## Suggested order

1. Fix findings 1 and 2 in the current branch. Both live in code already being
   touched, and 2 is a live hole.
2. Correct the `evaluate_js` invariant text in `INTERFACES.md` and
   `M1_PLAN.md` §5, and re-scope XV-19's proof to the real-browser round trip
   (finding 3). Documentation-honesty fix; no code change.
3. Record the frame-navigation decision (finding 5) explicitly in
   `DESKTOP_UI.md`, either way.
4. Then slice 1, with the hardening block, the observable-attachment-failure
   path, and ordered shutdown as first-class deliverables rather than
   afterthoughts.
