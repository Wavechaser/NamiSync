# Historical NamiSync UI mockup

Archived on 2026-11-10. This folder is historical reference, not a frontend
starting point, current product specification or maintenance target.

This interactive HTML/CSS/JS prototype explored a Fluent 2 desktop during the
transition from PySide6/Qt to WebView2. Its sample tasks, controls and layout
document that design exploration. The shipped app uses the packaged assets
under `namisync/interfaces/web/assets/`. [Current desktop behavior](../../DESKTOP_UI.md)

## Viewing it

Open `mockup.html` directly in a browser (double-click it, or drag it into
a browser window). It's fully self-contained — no build step, no server,
no external requests.

## Prototype design

- Kind/status colors (accent `#0078d4`, ok/fail, the k-update/k-move/
  k-conflict set) came from the earlier Qt prototype's `namisync/ui/theme.py`
  tokens.
- Typography is the Segoe UI Variable family, paired with Cascadia
  Mono/Consolas for paths and hashes — both native to Windows 11 and to
  what the app already used for its log/mono text.
- The prototype shows one dark theme.
- **Mica placeholder:** a real Mica backdrop can't be simulated in a
  browser (it's a live composited material, not a static color), so it's
  stood in here with a solid fill, `#1A2225`. That color is scoped to just
  the title bar and the tabs column — the two surfaces that would actually
  sit on Mica in the real app. The main content pane is a separate, opaque
  `#101010` card that floats on top of it, and the page around the whole
  window mockup uses its own plain neutral grays, unrelated to either (see
  the `:root` token block and the palette note at the bottom of the page
  for the full breakdown).
- No icon toolbar and no per-button icons.
- Real shadows, layered cards, and standard CSS transitions are fair game
  now — WebView2 is full Chromium, so nothing here is held back to stay
  within QSS's limits the way earlier passes of this mockup were.

The mockup's title bar controls are decorative. Its menu-bar dropdowns simulate
interaction using CSS.

## What's interactive

- **5 task cards** in the left rail, each a simulated state: a
  plan awaiting review, one mid-execution, a verification that found a
  missing file, a finished copy+verify, and a fresh empty task. Click a
  card to switch to it. The active card highlights as a filled rectangle
  (color-matched to the floating content card); inactive cards are a plain
  list with a hairline separator, no boxed-card look.
- **Sync | Integrity toggle** — each task retains its own view state
  independently, including the "hand off to Integrity on copy+verify
  completion, but Sync still shows the finished run" behavior (try it on
  the "Execution complete" card).
- **Setup form vs. summary card** — an unconfigured task shows the full
  editable Source/Target/Comments/mode-toggle form. Once a task has a
  source, it collapses into a read-only summary card (source/target text,
  a condensed 3-pill readout of mode/verify/deletion settings, and an
  **Edit** link that reopens the full form).
- The mode/deletion/verify toggle buttons, filter chips, the collapsible
  Log drawer, and inventory right-click context menu (with real
  enable/disable logic, e.g. "Restore acknowledged" only lights up on an
  acknowledged row) all work.

## History

Before archival, this prototype lived at `ui_mockup/mockup.html`. Use
`git log --follow -- docs/obsolete/ui_mockup/mockup.html` to follow its history,
or `git show <historical-commit>:ui_mockup/mockup.html` to inspect an earlier
version. New product design and implementation belong with the active owners.
