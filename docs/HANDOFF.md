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

## Execution-time findings (same day)

A separate measurement-only review of `7413a833` found no correctness defect
(413 focused drain/frontend cases pass). Alternating 10k batches show headless
at 93–99 s and the same GUI build at 110–167 s, so single-pair speed claims
are inside the noise. GUI cost is spread across the pipeline. A shorter GIL
switch interval, 200 ms result collection and turning off power throttling do
not remove it. Minimizing the window during execution recovers about half of
the GUI excess (batch 10: headless 105–107 s, visible 128–129 s, minimized
115–118 s) by removing ~43 s of renderer and GPU CPU. The remaining ~10 s is
in-process bridge and drain work: the hidden page still makes 92% of the event
pulls. A single minimized smoke run (177 s, worker partly on efficiency cores)
did not recur. PERFORMANCE "Execution time: GUI versus headless" has the
tables and limits. Evidence and registered GUI fixtures are under
`build/exec-time-20261109/`.
No product change was made.

## Operational context

Work took place in the existing `milestone1` worktree.
The pre-existing cadence recovery branch/evidence remains untouched; its
integration and measurement disposition is recorded in M1_PLAN, PERFORMANCE,
and commit `7413a833`. This task changes no prior performance conclusions.
