# EV-0041: M2-A2 desktop checks (2026-11-24)

Hand checks that [EV-0040](../EV-0040/README.md)'s drop and framing spikes left
for a person at the desktop. Diagnostic observations that inform designs, not
acceptance results; conclusions are in the Drag-and-drop Setup and Custom
title bar entries of [M2_PLAN](../../docs/M2_PLAN.md). Origin:
`build/m2-a2/drop/` and `build/m2-a2/framing/` at `b647a7c7`.

Profile: the PERFORMANCE reference machine (Windows 11 Pro 26200), CPython
3.13.17 from the development `.venv`, pywebview 6.2.1, WebView2 SDK
1.0.3856.49, runtime 158.0.4370.33 (EV-0040 ran on 157.0.4341.60). PowerToys
was not running.

## Explorer drops (user-driven, `spike.py`)

| File | Run | Observed |
| --- | --- | --- |
| `drop-log.explorer-prevent.jsonl` | unelevated, zones prevent default | Single folders, a file, two folders, a `D:` folder and `folder_ü_日本語` reached the host as full paths; drop #8 (source not identified) arrived empty; 12 items refused on count |
| `drop-log.explorer-no-prevent.jsonl` | unelevated, nothing prevented | No drop and no `NavigationStarting` reached page or host; every item opened in its default app |
| `drop-log.explorer-longpath.jsonl` | unelevated | `folder_a` arrived; the 437-character folder arrived empty |
| `drop-log.explorer-elevated.jsonl` | elevated host, drag from unelevated Explorer | Accepted: `folder_a` and the 251-character folder arrived as full paths; the 312- and 375-character folders arrived empty |
| `stderr-prevent.txt` | unelevated | pywebview's `on_script_notify` raising `ValueError: too many values to unpack (expected 3)` on each page message |

User observations, not logged: in prevent mode a drop outside the two zones
opened the item in its default app or a new Explorer window, except
`folder_ü_日本語`, which opened as a directory page in the user's Edge browser.

## Window framing (`proto.py --mode nonclient_carve`)

Agent-driven with real input:

| Check | Result |
| --- | --- |
| Win+Up | Maximized, caption buttons in place |
| Win+Left | Snapped to the left half; Snap Assist opened |
| Alt+Space with focus in the page, and after clicking the bar | Window menu opened |
| Window-menu Move and Size by keyboard | Both worked; Move restored the snapped window first |
| Tab | Cycled inside the page; never reached the caption buttons |

User-driven:

| Check | Result |
| --- | --- |
| Mixed DPI (monitor 1 temporarily set to another scale) | Checked; no problem reported |
| Dark to light switch | Mica lost: the window turned plain white until switched back to dark. Light to dark, and launching in either mode, showed Mica correctly |
| Caption-button hover | No hover highlight on minimize, maximize or close; hover is still detected (maximize opens Snap Layouts) and pressed states show |
