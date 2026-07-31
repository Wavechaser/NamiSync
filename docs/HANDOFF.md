# NamiSync Session Handoff

Date: 2026-07-31
Branch: `milestone1`

## Session Outcome

Committed and pushed the completed Stage 6 slice-0 reality spike as
`2040146` (`Validate Stage 6 pywebview host`), then addressed the independent
review in the follow-up change.

- Made native-guard attachment state explicit and sticky. Pywebview's
  swallowed `before_load` exceptions now leave a host-visible failure, dispatch
  reports attachment failure rather than an origin mismatch, and a partial
  subscription is not retried or duplicated.
- Hardened pywebview before native startup:
  `OPEN_EXTERNAL_LINKS_IN_BROWSER=False`, `ALLOW_FILE_URLS=False`,
  `ALLOW_DOWNLOADS=False`, `REMOTE_DEBUGGING_PORT=None`, and `debug=False`.
  This closes pywebview's earlier system-browser popup handler and pins the
  remaining host settings.
- Replaced name-based `WebViewException` rewriting with a synchronous
  `initialized` renderer check. Pywebview 6.2.1 silently selects MSHTML when
  WebView2 is absent; the wrapper now aborts that initialization and raises the
  actionable WebView2 error while unrelated startup exceptions propagate
  unchanged.
- Added `FrameNavigationStarting` and cancel every frame navigation, retaining
  first-in-`head` `frame-src 'none'` as the independent bootstrap control.
- Added full-URL origin derivation with `urlsplit`, including paths, queries,
  fragments, IPv6, explicit port zero, and strict rejection of non-HTTP
  authorities. Future code must pass `window.real_url` directly and must not
  trim it with `rsplit`.
- Corrected the bridge documentation: NamiSync code constructs no JavaScript,
  but pinned pywebview internally uses `evaluate_js` for exposed-function
  returns. Its escaper is now explicitly security-relevant and must be
  re-audited on every version change.
- Promoted the repeatable/unbounded bridge reinjection contract and entry-only
  dispatch authorization contract. `pywebviewready` initialization must be
  idempotent and re-arm one drain; completed-but-undelivered mutations retry
  with the original `command_id`.
- Moved the fully accounted review to
  `docs/obsolete/TMP_STAGE6_SPIKE_REVIEW.md` with a disposition banner.

No facade, workflow, dispatcher, core, module, database, schema, migration, or
CLI contract changed. The headed product window, packaged assets, event drain,
and launcher remain later Stage 6 slices.

## Verification

- Focused security spike: `23 passed in 0.06s`.
- Full repository: `829 passed in 26.47s`.
- Import boundaries: 49 files / 181 dependencies; all eight contracts kept,
  zero broken.
- Hidden real-host verification: pywebview 6.2.1 selected `edgechromium`, the
  synchronous renderer check ran, all four settings were hardened before
  native startup, `debug=False` was used, and the hidden window closed cleanly.
- Package health: `pip check` reported no broken requirements.
- `git diff --check` reported no whitespace errors; only expected LF-to-CRLF
  notices appeared.

## Immediate Next Context

Stage 6 slice 1 should preserve this order:

1. Create the pywebview window and one private JavaScript API object whose only
   public method is `dispatch`.
2. Register the zero-argument `initialized` callback that passes the complete
   `window.real_url` to `configure_pywebview2_security`.
3. Start only through `start_edge_chromium`; it hardens the settings, passes
   `debug=False`, and refuses the MSHTML fallback during `initialized`.
4. Let synchronous UI-thread `before_load` attach
   `NavigationStarting`, `FrameNavigationStarting`, `NewWindowRequested`, and
   `SourceChanged` before pywebview exposes application calls.
5. After `loaded`, inspect `NativeDocumentState.is_attached` and
   `attachment_error`; tear down with an actionable message if attachment did
   not succeed. Do not rely on callback exceptions propagating.

For slices 2–3, the real-browser hostile-name proof must traverse page
JavaScript → dispatch → pywebview's pinned return transport → production
`textContent` and read the exact rendered value back. Treat
`pywebviewready` as repeatable, keep at most one bounded `next_events` drain
per task, wake it during shutdown, and retry uncertain mutation delivery with
the original command receipt.

Do not reach `CoreWebView2` from setup or dispatch workers, restore
`get_current_url()` as authority, trim `window.real_url`, or add a
NamiSync-owned host-to-JavaScript data channel. The pre-existing executor
operation-safe-pause and audit-timeout parity decisions remain open in
`BUGS.md`.
