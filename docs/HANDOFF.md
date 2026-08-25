# Session Handoff

Status (2026-08-25): Stage 6 second-half checkpoint 0 and its pre-checkpoint-1
adversarial follow-up are complete. The accepted Bridge, scalar, retention,
Setup, task, review, inventory, and integrity targets remain inactive until
their named implementation checkpoints. Checkpoint 1 settlement-oracle work is
in progress and remains uncommitted.

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
- Reconciled the same revisions with BR-G-32: its current nine-row prose is now
  explicitly current-source truth, and its executable exact-order table plus
  JavaScript mirror advance at every command-activating checkpoint. BR-G-46
  remains specially reopened only for the checkpoint-4/6 revisions.
- Re-audited the retained findings against their DR-BRs, exact rows, checkpoint
  dependencies, and gates. No additional authority loop required redesign; the
  pass did expose and reconcile native file-identity narrowing plus missing
  typed outcomes for reachable scalar failures.
- Classified scalar guards by supported-platform reachability in `DEFENSE.md`:
  full-width file identity, timestamp, and aggregate-logical-byte boundaries
  remain reachable, while single-volume capacity and post-admission arithmetic
  are assertions rather than user-facing overflow states.
- Kept arithmetic in the signed-64 domain while defining opaque Windows file
  identity separately as canonical 128-bit text from one complete native
  adapter. Added exact plan logical-byte refusal and scanner timestamp-warning
  outcomes; later probes reuse their existing unavailable/unreadable states.
- Kept the event-v5 cut before checkpoint 4 because task results already depend
  on it, and split checkpoint 3 internally into consumer preparation, atomic
  producer/database reset, and legacy-removal commits with independently
  testable safe stops.
- Hardened H2 for cold-start delivery: every checkpoint now has one entry,
  evidence, activation, defect-fix, status, and handoff protocol; checkpoint 3
  keeps v5 unreachable at its first stop; checkpoint 4 predeclares retention
  and installs lifecycle machinery before activation; checkpoint 7 cannot
  expose a blind execution start; and checkpoint 11's named commit is its final
  closure after any separate policy fixes.
- Added only four distinct causal records to `BUGS.md`; existing entries already
  cover split protocol authority, publication compensation, retention, and
  lifecycle ownership classes.

## Verification

- Independent component, authority/status, Bridge, and final integration
  reviews completed during ratification; their actionable findings were
  corrected and rechecked.
- The Bridge retains 32 accepted Stage 6 target command rows. The command map
  is 12 unique production commands after checkpoint 4, 18 after checkpoint 6,
  and 36 after all target rows plus the four retained bootstrap/cosmetic rows
  are active.
- `tests/test_department_policy.py`: `16 passed`.
- BR-G-32's current exact production command-table test: `1 passed`.
- Repository collection during ratification: `2891/2919 tests collected`,
  `28 deselected`.
- Markdown consistency searches, exact command-row counts, and
  `git diff --check` passed for the follow-up correction.
- The second adversarial pass revalidated the retained authority findings,
  corrected the scalar/file-identity contract where it did not survive runtime
  comparison, checked checkpoint-3 dependency direction, and deduplicated the
  causal bug ledger.
- The in-progress checkpoint-1 settlement oracle passed all 30 scenarios in
  three identical runs; this does not close the checkpoint before its focused,
  department, diff, and independent projection review completes.

## Immediate Next Context

Checkpoint 1 is in progress in `docs/EXECUTOR.md`, `docs/TOOLS.md`,
`tests/test_tools_executor_settlement_audit.py`, and
`tools/executor_settlement_audit.py`. Finish its focused and executor/tools
department verification, independently review the pre-production projection,
then commit those four files under the named checkpoint-1 title and mark its
shell row complete. Do not start checkpoint 2 protocol or producer changes
first.
