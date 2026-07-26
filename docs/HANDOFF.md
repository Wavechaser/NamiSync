# NamiSync Session Handoff

Date: 2026-07-27

## Session Outcome

Aligned filtering with the live reviewed-plan architecture and simplified the
ledger-v2 inventory contract.

- Path filters remain immutable planning input applied symmetrically to fresh
  source and target scans, then frozen into the plan fingerprint.
- Retained inventory remains role-free physical and integrity evidence.
- Mapping state retains source/target correspondence used by move detection,
  without a second inventory-backed policy path.
- The ledger stays at schema version 2 with the renewed exact contract marker
  `m1-ledger-xxh3-128`. Existing databases carrying another marker must be
  reset explicitly under the existing pre-release policy.
- Code, schema, tests, and documentation now describe this single ownership
  model consistently.

## Verification

- Targeted schema, inventory, recorder, planner, settings, and workflow tests
  pass.
- The full pytest suite and import-boundary checks pass.
- Repository search finds no second inventory-backed path-policy implementation
  or obsolete contract marker.
- `git diff --check` passes.

## Immediate Next Context

M1 Stage 6 can build live plan filtering and reviewed operation selection on the
existing service/runtime seam. Inventory previews may evaluate display criteria
or a temporary plan filter over repository rows without persisting view state.
Named recurring mappings need only durable relationship identity until a
complete saved-task configuration is deliberately designed.
