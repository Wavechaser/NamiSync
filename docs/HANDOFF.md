# Latest session — M1-9 final integration

2026-10-02. Integration branch `milestone1`; original task base `937af54`.
The user authorized M1-9, allocated missing-row acknowledge/restore here, and
requested a stop after M1-9 for recap and GUI tweaks. No M1-10/release work is
activated. M1_PLAN owns current scope and decisions.

## Changes and integration

Six preceding reviewed commits: `ec3865c` projection/shared sibling ordering;
`12cae9b` cold evidence; `a84e816` bounded reads; `687549a` desktop reads;
`9266845` same-task Refresh; `978ddf1` conditional visibility actions.

`910255f` fixes shared admitted-start identity for Plan, inventory, Plan again
and serial pair-batch starts. It advances list generation, adopts active session
identity, replaces the old drain and keeps fresh Plan requests distinct from
execution. The reconstructed desktop candidate uses that helper for Refresh,
retains original-command recovery, and provides folder acknowledge/restore.
User narrowed the new native witness to real command clicks, displayed result
replacement, missing-row hide/return, screenshot and task/host Close.

Separate test maintenance is ready to commit: six exact command catalogs gain
seven inventory commands; three native-completion/join waits allow forty seconds
inside the unchanged sixty-second scenario bound. Original ten-second waits
expired before correctly canceled navigation completed. A failure-only diagnostic
and a bounded timing diagnostic establish the mismatch; actual unmodified gate
assertions then pass. No DNS, browser-update or GIL cause is claimed. Product
behavior and cancellation, identity, ordering and transport assertions are unchanged.
The desktop action candidate is separately reviewed and ready for final commit.

## Verification

Evidence root: `build/m1-9-20261001/`.

- `complete-ordinary-20261002.log`: 5,829 passed, four skipped, 35 headed excluded.
- `desktop-refresh-frontend-focused.txt`: 64 passed, six deselected. Seven shared
  start regressions and two permanent Refresh regressions retain red/green controls.
- `native-wait-ordinary.log`: 1,890 interface tests passed after the test-only
  maintenance; unaffected ordinary evidence is retained by dependency.
- Headed coverage is across affected runs, not one aggregate invocation:
  `complete-headed-20261002.log` supplies 30 unchanged passes; its AB-6 pass is
  superseded by `native-replacement-20261002.log` (one pass). Transport passes
  in `headed-recheck-20261002.log`; BR-G-30/31 pass in `native-wait-headed.log`
  (two passes). `inventory-headed-focus-ready.log` adds the new inventory pass.
  Total current coverage: all 35 required cases. Earlier failures remain retained.
- New inventory receipt proves trusted foreground-owned clicks, exact folder
  actions, replaced display, missing row hidden/back, screenshot, task Close,
  and normal host Close. Its final focus driver re-establishes button focus after
  foreground recovery and records seven facts before refusing. Current AST/JS
  parse receipt is `inventory-focus-parse-corrected.log`.
- `final-imports-20261002.log`: 12 contracts kept. Local document targets: 191
  checked, zero missing; anchors are not checked. Diff checks pass.
- Cold projection samples remain valid: five fresh runs each, maxima
  1.9712401/2.8123806 seconds below 3/6-second limits. No new timing was needed.

Independent receipts: `review-shared-start.md`,
`review-inventory-witness-corrected.md`, `review-desktop-actions-final.md`, and
`review-host-gate-maintenance.md`. Final document completion facts and commits
remain to be recorded. No native-input interval is active.

## Preservation and closeout

Recovery `4b936db` on `codex/wip-20261001-2242-m1-9-desktop` was not merged or
cherry-picked. Useful changes were reconstructed on the integration branch;
account for all saved paths before removing the recovery ref. No worktree or
unrelated changes exist. Thirty-four inventory receipt/identity files are copied
and hash-verified under `inventory-native-preserved/`. External task Temp roots
and other raw evidence remain retained, including failed and diagnostic runs.
No fixture cleanup or unrelated deletion has occurred. Finish reviewed commits,
condense M1_PLAN to delivered scope/evidence, update changelog/handoff, verify clean
status, then stop for the user's GUI review. The machine is idle; no further
measurements or native runs are currently needed.
