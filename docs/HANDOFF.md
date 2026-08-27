# Session Handoff

Status (2026-08-27): power-loss recovery remains safely anchored and the
checkpoint-4 planning-source prerequisite has been reduced to its current
narrow ownership contract. Checkpoint 4 is still before its first mandatory
reservation-model commit. Production still has exactly nine commands; no task
lifecycle, model constant, fixture, validator hash, measurement, or BR-G-45
acceptance has activated.

## Recovery and safe lineage

- The complete interrupted 19-path state remains preserved at Git object
  `33f699448b5940b2aa4b0464b3a238297c68ab86` on branch
  `codex/recovery-power-loss-20260827`. Do not delete it until checkpoint 4 is
  safely past its first model commit.
- Recovery restarted from `b457ef9`; adapter exception retirement landed at
  `1e52fb9`; the canonical plan vector landed at `a8be549`; and the first source
  wall landed at `5256f3f`. The current work simplifies the contracts introduced
  by `5256f3f`.
- Recovered provisional model totals, formulas, fixtures, and hashes remain
  non-authoritative and must not be reused.

## Narrow planning-source closure

- Independent raw scanner, mapping, assignment, operation, observation, and
  refusal populations stop at their first excess without accumulating
  disposable construction costs.
- Declared scans, correspondence, policy inputs and results, the plan, observed
  world, and verdict are detached exactly and revalidated at their distinct
  hostile seams. Correspondence queries are structurally bounded by admitted
  scans, and hostile correspondence output is captured exactly once. Callback
  input copies remain disposable.
- The retained ledger charges only final operation and information rows plus
  unavoidable simultaneous shallow slots in final scans, plan operations,
  dependencies, assignments, required volumes, world maps, and verdict
  refusals. Ordinary selection and exclusion behavior remains unchanged and is
  not a retained owner.
- The first `ReviewFactLimitError` becomes typed `REFUSED + UNRUN`; the plan
  saver is not called and no partial artifact is published.
- This prerequisite does not price construction, sorting or indexes, selection
  or previews, callback overlap, codecs or text, native or browser copies,
  object headers or container capacity, complete projections, exceptions, task
  artifacts, or multi-session retention. Checkpoint 4 owns those costs.

## Verification

- Focused source-wall and ordinary scanner/planner/preflight parity:
  `264 passed`.
- Exact `core`, `scanner`, `planner`, `preflight`, and `workflows` department
  union: `2,168 passed, 1 skipped, 2,705 deselected`.
- Ordinary repository suite with the required Node environment:
  `4,842 passed, 4 skipped, 28 deselected`.
- Import architecture: `11 kept, 0 broken`.
- Executor settlement oracle: all 30 scenarios passed three identical runs.
- `git diff --check` and targeted stale-term review passed. An independent
  post-simplification audit found no false refusals, double charging,
  unnecessary copies, redundant validation, misplaced policy, private-counter
  test coupling, or ordinary-behavior drift.

## Next safe work

1. Close the remaining raw exception owners before starting the reservation
   model: workflow recording `enter_error` and `exit_error`; planner and
   destination-policy failures that escape with producer frames; callback retry
   closures that retain first raw failures; and dispatcher worker or
   cancellation `BaseException` objects. Keep causal fixes in separate commits
   with weak-reference or traceback regressions and ordinary parity; do not mix
   them with model constants.
2. Proceed through checkpoint 4 in order:
   `test(web): pin task artifact reservation model`,
   `feat(web): install dormant task lifecycle`, then
   `feat(web): retain multi-session task artifacts`.
3. Derive a fresh complete ownership graph and validator from active source and
   `docs/M1_BRIDGE.md` plus `docs/DEFENSE.md`, never from the recovery snapshot.
   The second commit preserves the nine-row command table and one-session
   behavior. Only the third activates the 12-row map and six task rows. BR-G-45
   and SH-G-15 remain open until their owning acceptance work closes them.
