# Latest session — single-scroller migration complete

2026-10-13, milestone1; base ca31654. The user explicitly authorized the
single-scroller candidate despite AX1's unconfirmed cause, as one atomic,
independently revertible commit. AX2 is complete in the commit containing this
record. No backend, schema, prefetch, input-queue or Setup behavior changes.

Plan/execution and Inventory use one outer two-axis viewport with an opaque
sticky 24px header. Viewport arithmetic reserves that header, keyboard reveal
keeps rows below it, and focus restoration preserves scroll. Column tracks share
one gutter. Inventory retains the inner semantic tree and generic-tree defaults.
Direct page/native/gallery and loading-tool consumers migrated together.

Verification: interfaces/tools 2,385 passes with three existing privilege skips;
focused frontend 57, Inventory 2, loading controls 41 and final gallery controls 26.
Installed task shell default/larger passes 2, Inventory 1, generic tree plus
execution default/larger 3, and light/dark/forced gallery 1. Source manifests and
installed identities support evidence reuse; independent review found no
unresolved source or consumer regressions.

On resumption the user foregrounded the test windows. Unchanged axis-candidate-03
passed all 20 sequences/36 browser wheel events across both actual tables,
with full movement in isolated axes and both switch orders, correct sticky
geometry, stable rows and valid input ownership. Source/helper/wheel identities
remained unchanged; both hosts closed. Original physical wheel/tilt symptom and
Chromium attribution remain unverified. PERFORMANCE owns those limitations.

Evidence: build/single-scroller-20261012/. Earlier focused/native/gallery fixture
failures and candidate01/02 pre-input foreground refusals remain retained.
Shell02, inventory01, gallery02 and remaining01 are final native passes. Gallery
tail observation follows original count/appearance sampling; sticky test bounds
use the actual usable row area. No product edits followed the final broad pass.

Recovery dbcc686 on codex/wip-20261012-single-scroller was rebuilt from ca31654
on milestone1 via its task-only patch, then final documentation was rewritten;
the recovery commit was not merged/cherry-picked. integration.md records the
final identity and recovery cleanup after full change accounting. No unrelated
work or worktrees were involved. Prior loading 81731de and AX1 ca31654 remain
separate. Revert only the final AX2 commit to undo this migration.

Use justified host pwsh for tests; preserve foreground/hit checks and serialize
native windows. README and AGENTS are unchanged because milestone synopsis and
repository rules are unchanged. No active test processes or pending gates remain.
