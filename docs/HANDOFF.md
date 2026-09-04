# Session Handoff

Status (2026-09-05): the off-origin structured-refusal defect is fixed and
verified on `milestone1-anthony`. Exact native response-token acknowledgment is
now cleanup-only and independent of current document trust. No test acceptance,
command authority, readiness timing, or response-custody lifetime was weakened.

## Outcome

- Command dispatch still reserves its handler and then rechecks exact committed-
  origin trust. An off-origin command invokes no handler and returns the exact
  `bridge_unavailable` refusal.
- A matching response token can mark only its existing browser custody released.
  It returns no response content, admits no command, and does not permit reaping
  until that exact native worker exits.
- The browser can therefore acknowledge the detached refusal and classify it as
  `BridgeCommandError` instead of losing it behind `BridgeTransportError`.
- Native and browser regressions cover the causal boundary. The native regression
  failed at the expected false acknowledgment before the product change.

## Verification

- `tests/interfaces/web/test_bridge.py`: 52 passed.
- `tests/interfaces/web/test_transport.py`: 124 passed with the bundled Node
  runtime; the standalone interactive probe also passed.
- Interfaces department: 1,429 passed, 3,536 deselected.
- Ordinary suite: 4,933 passed, four established capability skips, 28 headed
  deselected.
- Import Linter: all 12 contracts kept.
- The exact installed off-origin headed witness observed `Off-origin dispatch
  refused`, then failed at its separate stale evidence-shape assertion: the
  child records the native wrapper while the parent expects the bare command
  envelope. That scaffold defect was not changed or represented as green.

## Remaining focused test work

- The bounded UI Automation observer retry remains preserved on
  `codex/wip-20260904-2300-uia-observer`; rebuild it as an ordinary commit rather
  than merging the recovery commits. Its prior fixture-only diagnosis is
  superseded by this product fix.
- The stale off-origin evidence-shape assertion is a separate test-fixture
  repair. The actual-text acceptance and exact intended-window ownership remain
  unchanged.
- TS-0 remains the only active simplification checkpoint. TS-1 through TS-11 are
  shelved. The accepted plan and inventories remain on
  `codex/wip-20260904-2142-test-simplification` until rebuilt and reviewed.
- Do not prune either WIP branch until every path has been accounted for as
  merged, superseded, or deliberately discarded.
