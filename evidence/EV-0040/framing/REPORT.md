# M2-A2 spike: window framing

Written by the orchestrator from the builder's final report (subagents may not
write report files). `out/nonclient_carve_hover_max.png` inspected: the Snap
Layouts flyout is open over the content-extended prototype; the DWM caption
buttons sit on a light strip over the dark page (caveat 7).

## Verdict: feasible on pywebview 6.2.1 + WebView2 without `frameless`

All three pieces are needed together (mode `nonclient_carve`):

1. `WM_NCCALCSIZE` subclass on the top-level form (SetWindowSubclass via
   ctypes, installed on the UI thread after `shown`): left/right/bottom as the
   system computes; client top = window top (restored) or window top + frame
   thickness (maximized). WS_CAPTION, WS_THICKFRAME, WS_SYSMENU,
   WS_MAXIMIZEBOX, WS_MINIMIZEBOX stay set; DWM still draws the real
   min/max/close buttons; Mica via the appearance.py recipe reads back
   backdrop type 2 in every mode.
2. WebView2 non-client regions: `CoreWebView2.Settings.IsNonClientRegionSupportEnabled
   = true` with CSS `app-region: drag` / `no-drag`; `Chrome_WidgetWin_0` then
   answers HTCAPTION over drag regions (drag, double-click maximize,
   right-click system menu).
3. `SetWindowRgn` hole in the WebView2 host control over the top 6 dip resize
   band (none when maximized) and the caption-button rectangle, so the
   top-level `WM_NCHITTEST` answers HTTOP/corners and
   HTMINBUTTON/HTMAXBUTTON/HTCLOSE there. Recompute on WM_SIZE and
   WM_DPICHANGED.

Neither alone works: without the WebView2 setting (`nchit_carve`) the drag bar
is dead; without the carve (`nonclient`, `nonclient_nchit`) WebView2 answers
HTCAPTION over the buttons, so HTMAXBUTTON (Snap Layouts) never happens and the
top edge is never asked.

Key risk confirmed: over web content the top-level `WM_NCHITTEST` is never
sent (0 messages logged with the real cursor on caption, max button, top edge,
body); `WindowFromPoint` returns `Chrome_RenderWidgetHostHWND` and every
ancestor answers HTCLIENT. Left/right/bottom edges work natively (invisible
border outside the client rect); the top edge does not after NCCALCSIZE.

## Versions

pywebview 6.2.1, CPython 3.13.17; bundled `Microsoft.Web.WebView2.Core.dll` /
`.WinForms.dll` 1.0.3856.49 (has `IsNonClientRegionSupportEnabled`); runtime
157.0.4341.60. Window chain: form → WebView2 control → `Chrome_WidgetWin_0`
(our process) → `Chrome_WidgetWin_1` (browser) → `Chrome_RenderWidgetHostHWND`.

## Evidence (primary display 3840x2160 at 175%; second monitor not measured)

Modes: baseline, nccalc, nchit, nchit_carve, nonclient, nonclient_nchit,
nonclient_carve; ~40 points each in `out/<mode>.json` (top-level result,
WindowFromPoint class/root, per-ancestor NCHITTEST chain, real-cursor logs).

| point | baseline | nchit (no carve) | nonclient_carve |
|---|---|---|---|
| left/right/bottom edge | native | same | same |
| top edge, corners | HTTOP / corners | right answer, never asked | right answer, real log HTTOP |
| caption drag | HTCAPTION | never asked | `Chrome_WidgetWin_0` HTCAPTION |
| min / max / close | native buttons | never asked | right answer, real log HTMAXBUTTON |
| body | HTCLIENT | HTCLIENT | HTCLIENT |

Button hit ranges (window x at 175%, 46 dip each): restored 1669–1750,
1751–1831, 1832–1913; maximized 3610–3689, 3690–3770, 3771–3850.

Real input on `nonclient_carve`: drag moved the window exactly (+90,+70);
double-click maximizes/restores; max button maximizes/restores; min button
iconifies; all edges and corners resize by the dragged amount; hover on max
shows the Snap Layouts flyout; right-click bar opens the system menu; maximized
client rect (0,0,3840,2076) equals the work area (baseline client top y=40).
`nchit_carve` shows no drag, no double-click, no menu. PrintWindow light/dark
captures show a black page and are not evidence for Mica.

## Blockers and caveats

1. A Win32 subclass (NCCALCSIZE, NCHITTEST, SIZE, DPICHANGED) is required in
   the host layer, outside pywebview.
2. Never touch `Control.Handle` or `CoreWebView2` off the UI thread (early
   intermittent hangs); use `window.events.shown`, then `Control.Invoke`.
3. DwmDefWindowProc is unreliable (HTCLOSE in the top band; min/close failed
   when maximized). Button rects are computed from the right edge of
   `DWMWA_CAPTION_BUTTON_BOUNDS` at 46 dip × scale each: an observation on build
   26200, not a documented constant; re-verify at 100/150/200%.
4. The carve goes stale unless recomputed on size/DPI change; WM_DPICHANGED is
   untested (one DPI available).
5. `IsNonClientRegionSupportEnabled` took effect only after a navigation; the
   product must set it in `CoreWebView2InitializationCompleted` before the
   first navigation, touching pywebview startup (same cost as the Native Fluent
   overlay scrollbars entry).
6. The top 6 dip band is not web content while carved: no controls there.
7. DWM buttons follow the form's DWM dark/light attribute, not page CSS; keep
   them in sync.
8. Alt+Space inconclusive: synthetic keys did not open the menu even in
   baseline (WebView2 holds focus).

## Interactive checklist

Launch `.venv\Scripts\python.exe build\m2-a2\framing\proto.py --mode nonclient_carve`
(compare `--mode baseline`):

1. Hover maximize 1 s: flyout; picking a cell snaps.
2. Alt+Space with focus in page and on bar opens the system menu.
3. Win+Arrow; dragging the bar to an edge snaps/maximizes.
4. Right-click bar: system menu; keyboard Move and Size work.
5. High contrast: standard buttons, readable bar, drag works, Mica falls back.
6. Mixed DPI: move between monitors of different scale; flyout, top band and
   carve realign (WM_DPICHANGED).
7. Windows light/dark: caption glyphs follow; Mica in both.
8. Tab never lands on DWM buttons; no stuck hover.
9. Minimize/restore, maximize on second monitor, close from taskbar thumbnail.

## Rerun

```powershell
pwsh -NoProfile -File build\m2-a2\framing\runall.ps1          # moves the real cursor
pwsh -NoProfile -File build\m2-a2\framing\run.ps1 -Mode nonclient_carve -Measure -Actions
.venv\Scripts\python.exe -I build\m2-a2\framing\show.py nonclient_carve caption max_btn
.venv\Scripts\python.exe build\m2-a2\framing\probe_sdk.py
```

Files: `proto.py`, `run.ps1`, `runall.ps1`, `show.py`, `showact.py`,
`probe_sdk.py`, `page.html`, `patch1.py`–`patch6.py` (build-time edit scripts),
`out\`, `run.log`.
