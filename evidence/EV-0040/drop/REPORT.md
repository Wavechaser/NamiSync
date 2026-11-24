# M2-A2 spike: drag-and-drop paths

Written by the orchestrator from the builder's final report (subagents may not
write report files); drop rows spot-checked in
`drop-log.prevent-on.selftest.jsonl`.

Files: `spike.py` (prototype: host handler, bounds, JSONL log, `--selftest`,
`--no-prevent`), `page.html`, `page_noprevent.html`, `read_log.py`,
`inspect_sdk.py`, selftest logs, `fixtures\` (folder_a, folder_b, file_1.txt,
`folder_ü_日本語`, f0–f5, a 437-character `longpath\`), `webview2-userdata\`.

## Versions

pywebview 6.2.1 (`gui="edgechromium"`); bundled
`Microsoft.Web.WebView2.Core.dll` 1.0.3856.49; runtime 157.0.4341.60.
Reflection: `CoreWebView2WebMessageReceivedEventArgs.AdditionalObjects`,
`CoreWebView2File.Path`, `CoreWebView2FileSystemHandle` and
`CoreWebView2Controller.AllowExternalDrop` (default True) exist.

## 1. Mechanism: confirmed with synthetic drops

Drops were driven with CDP `Input.dispatchDragEvent` using real paths; this is
not an OLE drag from Explorer.

- Page `drop` → `chrome.webview.postMessageWithAdditionalObjects(json,
  Array.from(dataTransfer.files))`; host `CoreWebView2.WebMessageReceived`
  reads `args.AdditionalObjects` as `CoreWebView2File` whose `.Path` is the
  full drive-qualified path.
- `FileSystemHandle` objects arrive as null through pythonnet: do not use them.
- The host can read `AdditionalObjects.Count` and the message length before
  parsing, so the bound belongs on the host (spike: 4 items, 8192 chars,
  refuse rather than truncate).
- Page-reported names and kinds are untrusted (a 437-character folder was
  reported as kind file). The host decides folder or file by its own stat,
  then normal admission.

## 2. What reaches the host (synthetic)

| Drop | Host received |
| --- | --- |
| one folder | one CoreWebView2File, full path, is a directory |
| one file | full path |
| two folders | two entries, full paths |
| `folder_ü_日本語` | Unicode path intact |
| 437-character folder | full path |
| six items | refused on Count |

A folder and a file both carry only `Path`; the page-side File has size 0
and empty type for a folder and for an empty file alike. Not yet covered: a
folder from another drive, UNC, a real Explorer multi-select.

## 3. pywebview interference and navigation

- pywebview hooks `WebMessageReceived` (`webview/platforms/edgechromium.py:104`,
  handler `:225-249`); it reads AdditionalObjects only for the message
  `"FilesDropped"` and only when its DOM drop listeners exist
  (`:229-242`, `webview/dom/element.py:413`), which NamiSync never registers.
  Its bare-name matching is `webview/util.py:288-300`.
- pywebview's handler also runs on our messages and tries to unpack non-
  `"FilesDropped"` JSON into three values (`:244`): harmless (a caught
  ValueError logged to stderr) for an object-shaped message, but a 3-element
  list would reach `js_bridge_call`. Use an object-shaped message.
- The event is multicast; attach our handler in `before_load` as
  `namisync/interfaces/web/bridge.py:541-572` does.
- pywebview never sets `AllowExternalDrop`; leave it True.
- Navigation on an unprevented drop was not reproduced synthetically. Chromium
  normally navigates to `file://` unless dragover/drop are prevented; the
  product's NavigationStarting guard (`bridge.py:447-470`) would cancel it.
  The page should prevent default on dragenter, dragover and drop, including
  on `window`.

## 4. Elevation boundary: not run

Expected under UIPI: unelevated Explorer cannot drop onto an elevated app;
nothing reaches page or host, so it cannot be detected. Treat as a documented
limitation pointing to Browse rather than widening the message filter.

## Interactive checklist (unelevated PowerShell, repo root)

```powershell
.venv\Scripts\python.exe build\m2-a2\drop\spike.py
.venv\Scripts\python.exe build\m2-a2\drop\read_log.py
```

Log: `build\m2-a2\drop\drop-log.jsonl` (truncated each launch).

1. `folder_a` on SOURCE → one DIR row with full path.
2. `file_1.txt` on DESTINATION → FILE, full path.
3. `folder_a` + `folder_b` on SOURCE → two DIR entries.
4. A folder from another drive (D:, E:, G:); UNC/mapped if available.
5. `folder_ü_日本語` → intact Unicode path.
6. Deepest `longpath\` folder → full path, is a directory.
7. Five or more items → `refused too-many-items`, no drop row.
8. Elevation (a person launches from an elevated PowerShell): drag from normal
   Explorer; record cursor and whether anything arrives. Also the reverse.
9. `spike.py --no-prevent`: drop a folder and a file; record
   `navigation-starting` / `url-after` rows.
10. Optional: an item from a zip, Quick Access or a library.
11. In prevent mode, drop outside the zones → no navigation.

Stray `msedgewebview2.exe` children after an abnormal exit: stop only those
whose command line contains `m2-a2\drop`.

## Rerun

```powershell
.venv\Scripts\python.exe build\m2-a2\drop\spike.py --selftest
.venv\Scripts\python.exe build\m2-a2\drop\spike.py --selftest --no-prevent
.venv\Scripts\python.exe build\m2-a2\drop\inspect_sdk.py
```
