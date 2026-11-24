# EV-0044: Restore-size drift cause and remedy (2026-11-24)

User-requested follow-up to the separate finding in
[EV-0043](../EV-0043/README.md): every maximize/restore cycle of the framing
prototype grew the restored height by 52 physical pixels. Diagnostic evidence
for [M2_PLAN](../../docs/M2_PLAN.md)'s Custom title bar entry; no product
change. Profile as EV-0043: Windows 11 Pro 26200 at 175% (168 DPI), CPython
3.13.17, pythonnet on .NET Framework 4.8.9363 (NamiSync's pinned `netfx`
runtime), pywebview 6.2.1.

## Cause

WinForms, not Windows or WebView2. On maximize, `Form` saves the restored
bounds as the **client** size, marking both "is client size" flags. On
restore, `Form.RestoreWindowBoundsIfNecessary()` turns that client size back
into a window size with `SizeFromClientSize`, which uses the stock frame of the
form's styles. A `WM_NCCALCSIZE` handler that removes the top non-client area
leaves the client 52 pixels taller than the stock frame assumes (caption 40 plus
top border 12 at 168 DPI). Each cycle therefore adds 52 pixels. Windows itself
restores correctly; WinForms then resizes the window again.

Evidence (`summary.json`):

- `drift.py` is a bare WinForms `Form` with no WebView2 and no pywebview. With
  the stock frame it restores to 1100×720 every time. With either
  `WM_NCCALCSIZE` variant (EV-0042's maximized inset or EV-0043's zero inset)
  it restores to 1100×772, then 1100×824. The same happens whether the driver
  uses `WM_SYSCOMMAND` or `Form.WindowState`.
- The extra size comes from a second `SetWindowPos` (1100×772, flags `0x16`)
  issued from `Form.RestoreWindowBoundsIfNecessary` → `Control.SetBounds`
  inside `Form.WndProc`, right after the system restore to 1100×720.
- WinForms' private state after maximize reads
  `restoredWindowBounds = {300,200,1076,708}`, `restoredWindowBoundsSpecified =
  All` and both client-size flags set to 1. 1076×708 is the actual client, and
  708 + 52 + 12 = 772.

## Remedy demonstrated

After WinForms handles `WM_SIZE` with `SIZE_MAXIMIZED`, set the form's private
`restoredWindowBoundsSpecified` to `BoundsSpecified.None`. The restore then
keeps Windows' own normal placement:

- `drift.py ... fix` (cleared from the driver) and `... hook` (cleared in the
  window procedure after `WM_SIZE`): 1100×720 on every restore, for the stock
  frame and both `WM_NCCALCSIZE` variants and both drivers.
- `framing-proto.py --fix-restore` (the EV-0042 prototype with pywebview and
  WebView2, maximized inset variant), cycled by `cycle.py`: without the flag
  720 → 750 → 779, with it 720 → 720 → 720. `cycle.py` is not DPI-aware, so it
  reads physical sizes scaled by 1/1.75 (52 → about 30).

The remedy writes a private field. NamiSync refuses any pythonnet runtime other
than .NET Framework 4.8, whose WinForms is frozen, so the field is stable for
the supported host; a missing field must leave the window untouched. Not
covered: EV-0043's padded candidate inside pywebview (the bare probe covers its
zero inset, not its padding), restores after a user resize while maximized,
mixed DPI and snapped restores. The public alternatives would be correcting
the size after restore, which shows a second resize, or overriding
`SizeFromClientSize` in pywebview's `BrowserForm`, which NamiSync does not own.

## Rerun

Put `drift.py` and `cycle.py` in a disposable `build/` folder and run with the
project venv: `drift.py <plain|nccalc|nccalc0> <syscmd|state> [fix|hook]`
writes `out-*.json` next to it. For the real prototype, run
`framing-proto.py --mode nonclient_carve --interactive [--fix-restore]` from a
copy of `build/m2-a2/framing/` and then `cycle.py 0`.
