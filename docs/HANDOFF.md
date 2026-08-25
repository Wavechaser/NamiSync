# Session Handoff

Status (2026-08-25): Stage 6 second-half checkpoint 0 is ratified and its
unrun-execution retry contract is reconciled. The accepted Bridge, scalar,
retention, Setup, task, review, inventory, and integrity targets remain
inactive until their named implementation checkpoints. Checkpoint 1 has not
started.

## Delivered

- Added `M1_SHELL_H2.md` as the newest detailed checklist for Slices 5–6 and
  early Slice 7. `M1_SHELL.md` retains shell order and gates; `M1_PLAN.md`
  records the accepted reslice status.
- Concentrated exact Stage 6 protocol and presentation shapes in the mapped
  `M1_BRIDGE.md` register. The map identifies owning DR-BRs and the exact
  superseded fragments; it does not create blanket precedence or activate the
  target early.
- Put the signed-64 scalar and retained-resource hard walls in `DEFENSE.md`
  §1.3. Architecture and Core carry concise pointers, and Core now states only
  the implemented decoder boundary and coordinated target cutover.
- Reduced component additions to local behavior, consequences, checkpoint
  coverage, and authority pointers. `FEATURES.md` contains product behavior;
  `TESTS.md` contains no parallel checkpoint, module, command, or case catalog.
- Reconciled selection authority after an unrun attempt: submission failure or
  terminal `disposition=unrun` reopens the unchanged plan at a new selection
  revision, while the first `disposition=ran` permanently consumes that
  selection authority. A retry creates a fresh commitment.
- Added identity-safe **Plan again** behavior through `activate_task_pair` and
  a new `start_plan`: reviewed volume identity is re-resolved server-side,
  setup options are reused, and neither stale display paths nor prior selection
  authority carry into the new task.
- Reopened BR-G-46's command-map clause with exact checkpoint totals, retained
  its completed cosmetic-state clause, and moved the checkpoint-0 findings
  record from this session handoff to the bottom of `M1_SHELL_H2.md`.

## Verification

- Independent component, authority/status, Bridge, and final integration
  reviews completed during ratification; their actionable findings were
  corrected and rechecked.
- The Bridge retains 32 accepted Stage 6 target command rows. The command map
  is 12 unique production commands after checkpoint 4, 18 after checkpoint 6,
  and 36 after all target rows plus the four retained bootstrap/cosmetic rows
  are active.
- `tests/test_department_policy.py`: `16 passed`.
- Repository collection during ratification: `2891/2919 tests collected`,
  `28 deselected`.
- Markdown consistency searches, exact command-row counts, and
  `git diff --check` passed for the follow-up correction.

## Immediate Next Context

Stop for the requested recap before checkpoint 1. Three decisions remain:

- Classify each signed-64 and checked-arithmetic clause by reachability on the
  supported platform. Keep reachable filesystem-index cases as hard walls;
  demote or remove unreachable sums rather than presenting equal urgency.
- Reconsider checkpoint 3 immediately before checkpoint 8. If it stays atomic
  in its current position, predeclare an internal landing order and safe stop
  points.
- Add concise cause-based `BUGS.md` entries for substantive findings from this
  audit; the defect ledger was intentionally not expanded during ratification.

After that recap, checkpoint 1 is the settlement-oracle extension for typed
recording attribution. Do not start protocol or task implementation first.
