# Session Handoff

Status (2026-08-13): the read-only early-shell audit has been implemented and
adversarially reviewed. The full default suite is green; the real installed
WebView2 transport gate also covers private raw receiver-name refusal and a
25-second `next_events` long poll running concurrently with another RPC and
settling during window close.

## Delivered

- Pywebview now receives `js_api=None` plus one exposed `dispatch` function.
  Command names and log projection are bounded, handler admission is capped at
  64, and shutdown quiescence is finite, ordered, retryable, and fail-closed.
- The web registry caps live tasks at 48. `close_task` is terminal-record-gated,
  stepwise, idempotent across uncertain delivery, and removes observation,
  session, plan, task, and start-receipt state. Admission compensation is
  retryable; drain and release recovery have finite delayed budgets.
- `start_plan` retains its original slot-id/policy wire intent, so an exact lost
  response replay succeeds even after volatile folder-slot expiry or eviction.
  The desktop payload boundary still refuses hidden `mirror`.
- Service close now shares the session-receipt lifecycle gate, preventing an
  in-flight receipt replay from crossing receipt invalidation at shutdown.
- The headed host holds non-reparse, delete-denying leases on its app root,
  logs/WebView2 directories, and both ready database mains. It revalidates the
  pair after binding and authenticates an activation HWND against the current
  executable or venv base interpreter. Predictable same-principal mutex or
  base-interpreter spoofing remains an explicit residual boundary.
- Fresh database initialization reserves mains and sidecars through Windows
  ownership leases. Failure cleanup uses `ReOpenFile` on the retained
  reservation for exact-object disposition, runs for `BaseException`,
  preserves foreign replacements, and reports incomplete cleanup without
  discarding interrupt identity.

## Verification And Review

- Focused bridge, host, command, drain, service, path, single-instance,
  database-pair, static frontend, and transport suites passed during the change.
- The complete non-headed pytest suite and import-boundary check passed after
  integration. Clean-wheel headed transport evidence passed all 5 tests and
  instance activation passed all 3; temporary caches are ignored and are not
  product artifacts.
- Independent adversarial review drove the terminal-delivery close guard,
  mandatory release despite a page stop, owner retention after failed
  quiescence, activation executable validation, and explicit finite recovery.

## Immediate Context

The product workflow UI remains at the existing Slice 4 boundary; this change
adds only lifecycle `close_task`, not plan/inventory presentation or execution
controls. Do not reintroduce a dispatcher `js_api` object, unbounded task or
handler state, pathname-only database rollback, or owner release before
complete service shutdown.
