# EV-0042: M2-A2 framing fixes and drop prototype (2026-11-24)

Follow-up to [EV-0041](../EV-0041/README.md), whose framing hand checks found
two defects. Diagnostic observations that inform the Custom title bar design,
not acceptance results; conclusions are in [M2_PLAN](../../docs/M2_PLAN.md).
Same profile as EV-0041 (Windows 11 Pro 26200, CPython 3.13.17, pywebview
6.2.1, WebView2 SDK 1.0.3856.49, runtime 158.0.4370.33).

Further user checks, after EV-0041: high contrast and minimize, restore and
close from the taskbar work; high contrast also showed no caption-button
hover. The shipped M1 app shows neither defect.

| File | What it is |
| --- | --- |
| `framing-proto.py` | `build/m2-a2/framing/proto.py` with `--fix-theme` and `--fix-hover` |
| `framing-theme-reapply.txt` | Its log of each reapply after a theme change |
| `framing-maximized-hit-trace.json` | Hit-test counts and the last 400 hit tests, ending with a sweep across the maximized caption buttons |
| `drop-spike.py`, `drop-page.html`, `drop-page-noprevent.html`, `drop-read-log.py` | The drop prototype behind EV-0041's Explorer runs |

With these and EV-0040, `build/m2-a2/` can be cleared without losing a
prototype.

## Causes and fixes

- **Mica lost on a dark-to-light switch.** pywebview 6.2.1's form subscribes
  to `UserPreferenceChanged` (`webview/platforms/winforms.py:311`,
  `:330-339`) and sets `DWMWA_SYSTEMBACKDROP_TYPE` to Mica in dark mode but to
  none in light mode. The prototype set Mica only at launch, after pywebview's
  first call. With `--fix-theme` it reapplies dark mode and Mica after
  pywebview's handler on every change (the backdrop reads back 2 each time),
  and the user saw Mica through repeated switches both ways. M1's appearance
  observer already does the equivalent.
- **No caption-button hover.** The prototype answered caption-button hit
  tests itself and never passed `WM_NCHITTEST` to `DwmDefWindowProc`, which is
  what draws hover. Forwarding mouse messages alone did nothing:
  `DwmDefWindowProc` declined every `WM_NCMOUSEMOVE` and `WM_NCMOUSELEAVE`.
  With `--fix-hover` every `WM_NCHITTEST` goes to `DwmDefWindowProc` first
  while the prototype still returns its own answer. Hover then works on
  restored and snapped windows (agent-observed close highlight; user check of
  all three buttons), and clicks and Snap Layouts are unchanged.
- **Maximized windows: not fixed.** `DwmDefWindowProc` declined all 156
  maximized hit tests in the trace, including the sweep across the caption
  buttons (window rect `-12,-12,3852,2088`, caption-button bounds
  `3592,0,3851,51`), so a maximized window still shows no hover.
