# Latest session — scroll adoption verified; atomic integration in progress

2026-10-10. Original milestone1 base was
`59e92ae418ac0ca91dad46c3be35f046a6fe722e`; recovery changes were reconstructed,
not merged/cherry-picked. SW1 now passes its required gate and fresh review.

The full task-shell check `sw-task-shell-20261010-02` passed after a fixture-only
wait correction. Ctrl+Shift-click targeted an already highlighted row, so its old
predicate passed before the async highlight response replaced that row and
correctly dismissed the menu. A foreground-owned diagnostic proves the race.
The fixture now waits for the old invoker to disconnect and its highlighted
canonical replacement before native menu input. All focus/menu/input assertions
remain. Eight ordinary helper tests pass; failed receipts remain retained.

Prior unaffected evidence: 59 frontend, 1,979 interfaces, installed Inventory and
tree. Product source is unchanged from those runs. SW2 measurements, independent
reviews and SW4 ignored cache prototype remain under
`build/scroll-window-study-20261009/`. SW2 source/method checks: 37 focused and
402 tools passed, three skips. PERFORMANCE contains reviewed values and limits.

Commit SW1 product/probes/native consumers/docs with only the first
`table_loading.py` signature hunk, then SW2 collector/probe/test and results as
its own commit. Recovery ref `codex/wip-20261009-scroll-window-01` retains
`f6fbaeb` (including final fixture correction); remove only after full accounting.
No other dirty work, push, PR or worktree. No prefetch, row-schema, renderer or
bridge-cache product change. No process remains active. Installed assets were
restored; retain ignored evidence and baseline/candidate installations.
