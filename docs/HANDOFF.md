# Latest session — linked Verify toolbar, 2026-11-09

## Delivered change

Base `7413a833`, branch `milestone1`. Linked Verify retains the shared Filters
control, disabled with inherited Plan filters/counts, so Search occupies its
usual right-hand toolbar column. Entering linked Verify closes an open Plan
filter popup; returning to Plan restores normal filtering. The production
change is confined to Plan review rendering.

## Verification

The original renderer failed the focused visibility regression. The corrected
Plan probe and Plan review tests pass (52 cases), preserving the pre-existing
uninterrupted row-focus round trip. The full interface department passes:
2,289 passed, 4,237 deselected. Evidence is under
`build/linked-toolbar-20261109/`.

Installed gallery checks measure linked versus Plan Search width/right edge at
default and minimum window sizes in light, dark and forced colors. The final
installed gallery gate passes (one pytest case covering all three modes).
Independent review approved the production and corrected test changes.

Initial focused tests encountered sandbox Temp-directory creation failure;
the focused rerun used a fresh workspace Temp, while the full department used
normal Windows Temp with approved access. Initial gallery layout assertions
passed, but the added pane-switch measurement queued an outside scroll before
existing popup checks and closed their menu. The measurement now runs after
existing interactions; all original assertions remain. Initial receipts and
failures are retained in `gallery-initial/`, `headed.xml` and focused logs.

## Operational context

Work took place in the existing `milestone1` worktree.
The pre-existing cadence recovery branch/evidence remains untouched; its
integration and measurement disposition is recorded in M1_PLAN, PERFORMANCE,
and commit `7413a833`. This task changes no prior performance conclusions.
