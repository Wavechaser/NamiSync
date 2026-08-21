# Session Handoff

Status (2026-08-21): truthful executor and verifier per-item progress is
implemented, hardened against the six review findings, and accepted by the
production browser validator. Slice 5 still owns stable row projection,
identity mapping, follow behavior, and visual consumption.

## Delivered

- Kept core event schema v3 for the co-packaged current-source swap. Current
  serialization and the browser require the exact nine-key `Progress` body;
  Python's pre-change five-key decode is a defensive direct-codec allowance,
  not a supported production compatibility path.
- Made executor attempt bytes begin only at actual copy-stream entry and reset
  only when a retry or resumed run re-enters that pipeline. Aggregate high-water
  is reviewed-content bounded, retained in `ExecutionSet`, and carried through
  strict workflow payload v5 plus the resumed phase-total projection.
- Defined executor control boundaries without changing protected legacy
  progress semantics. Pause refreshes nominal item/attempt fields over the last
  emitted legacy totals/path while retaining live high-water for resume;
  cancel/exception repeats that legacy view and clears nominal item state.
  Normal completion still force-emits its live inactive final snapshot.
- Made `item_type` identify the opaque row-id namespace: executor and linked
  post-copy ids use `operation`, while standalone verifier rows use
  `integrity`. Item-stream overshoot preserves identity but removes the
  determinate byte pair; executor aggregate work remains reviewed-content
  bounded while verifier aggregate work expands for physical rereads.
- Returned verifier item/stream/settlement transitions to the ordinary throttle
  path. Successful runs have exactly two forced source boundaries independent
  of item count; pause and cancellation add one forced control boundary, with
  verifier pause publishing its live reporter state.
- Made the packaged drain-manager Progress validator/replay probe an ordinary,
  non-skippable JavaScript gate. It resolves `NAMISYNC_TEST_NODE` before `PATH`
  and proves malformed Progress rejects a whole batch before reliable sibling
  delivery or cursor movement, then clean replay delivers those siblings once.

Dispatcher loss/coalescing, history refusal, CLI aggregate rendering, bridge
commands, and database schemas remain unchanged. Workflow changes are limited
to the strict progress-high-water continuation and matching phase totals.

## Review

- Each checkpoint received an adversarial review. The six reported findings
  closed terminal phantom identity, undocumented/stale pause telemetry,
  post-copy namespace misclassification, item-total overshoot disagreement,
  verifier forced-emission amplification, and non-executable default browser
  validation.
- The protected executor settlement oracle then caught two subtler regressions
  in proposed terminal/pause handling: throttle-hidden legacy totals/path must
  not be refreshed on control unwind, while nominal item telemetry must be.
  `a64bc1f` preserves that split and adds cancel/exception equality guards.
- The active-document sweep updated the exact workflow payload/gate contracts,
  development Node prerequisite, module behavior, feature summary, bug ledger,
  task history, and immediate continuation context. The README milestone
  synopsis remains unchanged because Slice 5 presentation is still open.

## Verification

- Required packaged Node validator/replay probe: exit 0.
- Core/workflow/executor/verifier neighborhood: 819 passed, 1 skipped.
- Executor plus core departments after the control-unwind correction: 488
  passed, 1 skipped.
- Verifier plus workflow departments: 337 passed.
- Interface department: 1,133 passed.
- Schema/facade guard: 113 passed.
- Executor settlement oracle: 30 scenarios x 3 identical protected-baseline
  runs.
- Import-linter: 11 contracts kept, 0 broken.
- Ordinary repository after `a64bc1f`: 2,707 passed, 4 skipped, 28
  deselected.
- Real WebView2 headed interface gate: 28 passed, 2,711 deselected.

## Commits

- `48b0fbb feat(core): extend progress item telemetry`
- `c0df4e0 feat(executor): emit retry-aware item progress`
- `4d6341e feat(verifier): emit attempt-local item progress`
- `70e8ec0 docs: record per-item progress delivery`
- `c806d64 fix(executor): clear terminal item progress`
- `697c063 fix(executor): preserve progress across pause`
- `cbb3dd8 fix(progress): align identity and overshoot semantics`
- `849c9b6 perf(verifier): throttle item lifecycle progress`
- `a79eadb test(web): require executable progress validation`
- `a64bc1f fix(executor): preserve legacy progress on control unwind`

## Next Checkpoint

- Add stable operation/integrity row ids to the validated Slice 5 projection,
  map the nominal `item_type`/`item_id` pair to those rows, and render active
  determinate versus indeterminate states without joining on `current_path`.
- Icons and their existing fixed local infrastructure, explanatory tooltips,
  and click-to-copy full hashes remain intentionally shelved.
- Developers running the ordinary suite must keep Node available through
  `NAMISYNC_TEST_NODE` or `PATH`; the required Progress gate no longer skips.
