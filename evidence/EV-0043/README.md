# EV-0043: Maximized native caption investigation (2026-11-24)

User-requested follow-up to [EV-0042](../EV-0042/README.md), at
`bd005c07b9f83f0184037fdfe07b10fd030a3b99`. Diagnostic evidence for
[M2_PLAN](../../docs/M2_PLAN.md)'s Custom title bar entry; no product change or
release acceptance. The final probe and comparison drivers are retained here;
the immutable EV-0042 prototype supplies the underlying pywebview host.

## Findings

The maximized top inset in `WM_NCCALCSIZE` causes the hover failure on this
profile. Both the original 12-pixel inset and a one-pixel inset make
`DwmDefWindowProc` decline all 600 sampled points. Calling the ordinary window
procedure first, returning zero from NCCALCSIZE, reapplying full-frame extension,
or using a 64-pixel top extension does not recover it. Removing the top inset
does: 80 points each return HTMINBUTTON, HTMAXBUTTON and HTCLOSE, both with the
default NCCALCSIZE return and with the final candidate. The other 360 grid
points lie outside the buttons. The stock-caption control also declines DWM
hit tests; this does **not** mean stock caption hover fails.

The zero inset puts the client origin at `(0,-12)`. WinForms top padding of 12
physical pixels moves the docked WebView back to `(0,0)` without introducing
non-client space. Its rectangle then equals the visible frame
`(0,0,3840,2076)`. Padding returns to zero on restore. Update it and the child
region after size/DPI changes. No custom button drawing is involved.

The old `DWMWA_CAPTION_BUTTON_BOUNDS` conversion also undersizes the maximized
cutout: adding the window origin yields bottom 39, while native button
rectangles end at screen y=50. The final candidate uses `WM_GETTITLEBARINFOEX`
screen rectangles for the maximized child-region holes and honors DWM's handled
hit result. The native rectangles were Minimize `(3594,0,3676,50)`, Restore
`(3676,0,3757,50)` and Close `(3757,0,3840,50)`. All four inside corners and
the center of each rectangle returned the correct button code; `WindowFromPoint`
selected the form at all 15 points, including the rightmost screen pixel.
The matrix itself ran occluded, so its receiver observations were discarded;
this routing result comes from the separate foreground check.

The user checked all three highlights, the lower button edges, Snap Layouts,
alignment and restore/maximize on the padded candidate and reported
"All look right." That check preceded the refinement from a metric-adjusted
cutout to exact TITLEBARINFOEX rectangles. The final refinement passed the
15-point foreground check; agent input also restored, maximized and
double-click-maximized it, with layout visually inspected. Restored hit testing
and carving delegate to the previous prototype. This follow-up does not claim
fresh snapped-window, mixed-DPI, high-contrast or auto-hide-taskbar acceptance.

## Separate existing finding

Fresh processes tested two maximize/restore cycles. Both baseline and candidate
grew restored size from `1925x1260` to `1925x1312` and `1925x1364`. Native
WM_SYSCOMMAND transitions produced the same result as WinForms WindowState.
Thus the observed 52-pixel-per-cycle growth predates this hover candidate; it
was not merely contamination from switching frame modes in the matrix.
Root cause and remedy were not investigated. Carry it into title-bar host work;
do not treat this spike as acceptance of restore-size fidelity.

## Reproduction and records

`summary.json` compacts the matrix, geometry, boundary checks and restore-cycle
finding, with runtime and source identities. `compact.py` checks those
observations before writing the summary. It is a diagnostic consistency check,
not a product validator. The initial compaction had an incorrect path to the
restore logs; correcting it to `out/` allowed all assertions to run and pass.

For reruns, create disposable `build/m2-a2-maximized/` and
`build/m2-a2-max-clean/` workspaces with AGENTS.md rules putting scripts at their
root, logs/pages/profiles below them, and cleanup after process exit. Copy the
four scripts here into the former. Run `probe.py` with the project venv; it
copies EV-0042's baseline into the working folder before importing it. A
`command.json` file selects variants; `matrix.ps1` sends the eight named cases.
To reproduce the foreground/restored checks, copy the candidate configuration
from `summary.json` to that command file with names `m09-foreground` and
`m10-restored`, after foregrounding/maximizing or restoring the window. Input
automation that raises a window may restore it, so check the recorded state.

`fresh-check.py` generates a self-closing fresh-process probe under the second
workspace. Its default, `baseline` and `native` arguments generate `probe.py`,
`probe-baseline.py` and `probe-native.py`, respectively. Run each generated
script once, then run `compact.py`. The final interactive candidate was left
open for further inspection; it can be closed normally. All generated data is
disposable after the process exits.

## Primary-source cross-check

- [Microsoft's custom-frame sample](https://learn.microsoft.com/en-us/windows/win32/dwm/customframe)
  supports keeping native DWM caption controls with client content extended
  into the caption.
- [Chromium's native-frame handler](https://chromium.googlesource.com/chromium/src/+/ea1232d83ab12ebfbbb014129bf174a1259e6506/ui/views/win/hwnd_message_handler.cc)
  explicitly documents loss of caption hover/click processing when non-client
  space is left above a maximized custom frame. It also cautions against
  WVR_REDRAW with non-client insets. This source motivated the zero-inset
  experiment; the local comparison establishes the result on this profile.
- [DwmDefWindowProc](https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/nf-dwmapi-dwmdefwindowproc)
  owns native hit handling and must receive WM_NCMOUSELEAVE to clear highlights.
- [TITLEBARINFOEX](https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-titlebarinfoex)
  supplies individual button rectangles in screen coordinates.

Adversarial review checked the window/client/child coordinate conversions,
right and bottom edge coverage, real input receiver, padding removal, restored
delegation and the difference between DWM API return values and visual hover.
It found the separate restore-size issue above. No custom rendering, style-bit
spoofing, DWM hooking, synthetic hover shim or new runtime dependency is needed
for the demonstrated maximized-hover solution.
