# NamiSync Session Handoff

Date: 2026-07-21

## Session Outcome

Plan review now exposes the actual target-side origin of rename-shaped
operations. `PlanOperationView` retains `prior_target_path`, the local workflow
runtime populates it from `PlanOperation.prior_target_rel_path`, and the CLI
prefers it over the source path when rendering an operation.

A case-only operation therefore renders as `keep.txt -> KEEP.txt` instead of
the misleading `KEEP.txt -> KEEP.txt`. The same presentation fix applies to
ordinary `move` and `move_update` rows, which previously hid their old target
path.

## Changes

- Added nullable `prior_target_path` to the interface-facing plan-operation
  read model and populated it at the sole workflow construction boundary.
- Made plan rendering select the prior target as the displayed origin when it
  exists, while preserving existing source-to-target rendering for all other
  operations.
- Added CLI regressions for recase, move, and move-update rendering plus a
  workflow-boundary assertion that prior-target evidence survives translation.
- Updated command-line, interfaces, workflow, feature, bug-log, README, and
  handoff documentation.

## Verification

- Focused CLI/workflow suite: 26 passed in 2.03s.
- Full suite: 308 passed in 7.94s.
- Import-linter: 7 contracts kept, 0 broken (41 files, 137 dependencies).
- `git diff --check`: clean apart from expected LF-to-CRLF notices.
- Plan fingerprints, payloads, selection, commitment, and execution semantics
  are unchanged.

## Immediate Next Context

- `prior_target_path` is an interface read-model field, not a new serialized
  plan field; retained plan payloads already carry `prior_target_rel_path`.
- Future desktop/API plan renderers should use the same precedence as the CLI:
  prior target when present, otherwise source path.
- Source casing propagation remains disabled by default and unexposed. This
  change only makes opted-in recase review meaningful; it does not alter when a
  recase operation is planned or executed.
