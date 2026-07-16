# NamiSync UI Mockup

A single-file, interactive HTML/CSS/JS mockup of the NamiSync desktop app,
used to iterate on visual design before touching the real PySide6 UI. It is
a design artifact, not shipped code — nothing here is imported by
`nami_sync`, and this folder isn't part of the app.

It lives outside `docs/` deliberately: `docs/` documents the shipped app,
and this mockup is expected to move, get replaced, or disappear once the
overhaul it's exploring lands as real Qt code.

## Viewing it

Open `mockup.html` directly in a browser (double-click it, or drag it into
a browser window). It's fully self-contained — no build step, no server,
no external requests.

## What it's grounded in

Every color, font, column width, and label is pulled from the real app as
of the Phase 2 / menu-bar overhaul (`nami_sync/ui/theme.py`,
`task_page.py`, `main_window.py`; see `docs/UI_overhaul.md` and
`docs/GUI.md`), not invented:

- Palette is `theme.py`'s actual tokens (`#0f0f10` window, `#0078d4`
  accent, the exact kind/status colors), not a fresh design-system pass.
- Typography is Segoe UI (the app's real Fusion default) paired with
  Consolas for paths/hashes (already the app's own log font).
- Dark-only, by the same deliberate choice `docs/GUI.md` states for the
  real app ("A light mode is intentionally not implemented") — this mockup
  doesn't attempt a light theme either.
- No icon toolbar and no per-button icons, matching the explicit "no icon
  toolbar" stance in `docs/UI_overhaul.md` §9.
- No box-shadows, gradients, letter-spacing, or transitions beyond what
  Qt's QSS can actually render — the goal is that what you see here is
  close to what's buildable, not a browser-only fantasy.

**Mockup-only liberties** (won't exist in the real app, purely for
context/navigation here): the fake window title bar and traffic-light
controls, and the menu-bar dropdowns opening/closing smoothly — Qt's own
native menus will look and animate differently.

## What's interactive

- **5 task cards** in the left rail, each a different real app state: a
  plan awaiting review, one mid-execution, a verification that found a
  missing file, a finished copy+verify, and a fresh empty task. Click a
  card to switch to it.
- **Plan | Inventory toggle** — each task retains its own view state
  independently, including the "hand off to Inventory on copy+verify
  completion, but Plan still shows the finished run" behavior from
  `docs/UI_overhaul.md` §6 (try it on the "Execution complete" card).
- Filter chips, the collapsible Options/Log drawers, and inventory
  right-click context menu (with real enable/disable logic, e.g.
  "Restore acknowledged" only lights up on an acknowledged row) all work.

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
