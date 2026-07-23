# NamiSync UI Mockup

A single-file, interactive HTML/CSS/JS mockup of the NamiSync desktop app.
It's a design artifact, not shipped code — nothing here is imported by
`namisync`, and this folder isn't part of the app.

It lives outside `docs/` deliberately: `docs/` documents the shipped app,
and this mockup is expected to move, get replaced, or disappear once the
overhaul it's exploring lands as real UI code.

**Stack decision:** the desktop UI is moving from PySide6/Qt (Fusion style,
QSS) to a **WebView2**-hosted shell. That drops QSS's rendering ceiling, so
this mockup is no longer a simulation of what Qt could approximate — it's
now written in the actual technology (HTML/CSS/JS) the shipped UI will
render with, styled to the **Fluent 2** (Windows 11) design language.

## Viewing it

Open `mockup.html` directly in a browser (double-click it, or drag it into
a browser window). It's fully self-contained — no build step, no server,
no external requests.

## What it's grounded in

- Kind/status colors (accent `#0078d4`, ok/fail, the k-update/k-move/
  k-conflict set) are carried over unchanged from the app's existing
  `namisync/ui/theme.py` tokens, not a fresh design-system pass.
- Typography is the Segoe UI Variable family, paired with Cascadia
  Mono/Consolas for paths and hashes — both native to Windows 11 and to
  what the app already used for its log/mono text.
- Dark-only, matching the "Theme And Layout" stance in `docs/DESKTOP_UI.md`
  — this mockup doesn't attempt a light theme either.
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

**Mockup-only liberties** (won't exist identically in the real app, purely
for context/navigation here): the fake window title bar's minimize/
maximize/close buttons are decorative placeholders (real WebView2 caption
buttons behave natively), and the menu-bar dropdowns opening/closing here
are a plain CSS simulation of what a real menu implementation would do.

## What's interactive

- **5 task cards** in the left rail, each a different real app state: a
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

## Iterating without losing earlier attempts

This folder intentionally has **one canonical file**, `mockup.html` — not
`mockup_v1.html`, `mockup_v2.html`, `mockup_current.html`. A pile of
parallel near-duplicate files is easy to let drift (forget to update the
"current" one, end up unsure which is newest). Instead:

- Every meaningful design pass is a **git commit** to `mockup.html`, with
  a commit message describing what changed and why.
- To see history: `git log --oneline -- ui_mockup/mockup.html`
- To see what changed in a pass: `git show <hash> -- ui_mockup/mockup.html`
- To roll back to an earlier look (discarding later changes):
  `git checkout <hash> -- ui_mockup/mockup.html`
- To just *view* an old version without touching the working file:
  `git show <hash>:ui_mockup/mockup.html > /tmp/old.html` and open that.

If a particular version turns out worth keeping side-by-side for a longer
comparison (not just "the last commit"), tag it — `git tag
mockup-<short-description>` — rather than copying the file. That keeps the
folder at one file while still giving any past version a memorable,
directly checkoutable name.
