# NamiSync Session Handoff

Date: 2026-07-30
Branch: `milestone1`

## Session Outcome

Completed a comprehensive integrated adversarial review of the landed M1 stack
described by `M1_PLAN.md`, `HASH_REFACTOR.md`, and `M1_BRIDGE.md`, excluding the
still-unimplemented Stage 6 WebView2 desktop shell.

The reviewed implementation and permanent regressions are in commit
`a5e6ece` (`Harden integrated M1 invariants`). This follow-up handoff replacement
is the next documentation-only commit on the same branch.

No database schema, migration, ledger contract, or history contract changed.
The complete fixed/open defect record is in `BUGS.md`; focused component
documents and the README now match the reviewed behavior.

## Fixed Findings

- **Execution atomicity and idempotency:** MOVE/MKDIR now revalidate their
  reviewed source subjects; MOVE/RECASE bind the post-rename result to the exact
  reviewed old target; pure MOVE recording accepts target timestamps that were
  intentionally only granularity-equal to the source; resume/cancel and
  pre-recording paths release exact runtime custody and settle the ledger.
- **Inventory and persistence:** incomplete full/stale integrity refreshes
  refuse before verification; exact PATHS reconciliation covers unsupported
  rows and reappearance; multi-batch inventory reads use one SQLite snapshot.
- **Dispatcher and history isolation:** state transitions and their reliable
  events are serialized; subscribe/close cannot orphan a stream; audit observer
  construction failure degrades only the audit axis; entry-checkpoint resumed
  cancellation uses the workflow-owned retained-payload settlement.
- **Facade and shutdown concurrency:** every session-start family is
  command-id single-flight; receipt lookup/publication/removal is linearized
  with dispatcher retention; a closed facade cannot repopulate runtime state;
  incomplete dispatcher shutdown, observer join timeout, runtime dependency
  close failure, and concurrent close retries are all recoverable and cannot
  report false cached success.
- **Protocol boundaries:** core events, inventory/integrity continuations,
  semantic settings, and the web security spike reject coercive scalar types,
  duplicate keys, non-finite numbers, invalid Unicode, and unknown/missing
  schema fields before handler or domain execution.

## Open Design Decisions

Two defects remain open because either fix changes a product contract:

1. **Pause after a durable UPDATE/MOVE_UPDATE retry sub-step.** A pause after an
   update backup or move-update publish loses the process-local sub-step
   continuation; resume can then reject the executor's own mutation. Options:
   serialize the operation-local continuation, roll back the owned durable
   stage before honoring pause, or defer pause until the operation reaches a
   safe boundary. For M1, deferring pause to the operation boundary is the
   smallest safety-preserving contract; persisting sub-step state is the more
   capable but materially larger design.
2. **Audit-timeout live/retained parity.** A history write that completes after
   the acknowledgement deadline can persist provisional `audit=ok` after the
   immutable live terminal has correctly settled `audit=degraded`. Options:
   cancel/compensate the late write, add a deadline-aware settlement handshake
   that persists the final axis, or explicitly relax live/reopened parity.
   Relaxing parity would make history misleading and should not be the default.

Both are recorded as OPEN in `BUGS.md`; no silent workaround was introduced.

## Verification

- Full repository: `814 passed in 26.76s`.
- Focused final lifecycle set: `69 passed in 2.69s`.
- Import boundaries: 49 files / 181 dependencies; all eight contracts kept,
  zero broken.
- Independent builder/reviewer passes found no remaining concrete
  straightforward lifecycle defect after the final observer retry fix.
- `git diff --check` is clean apart from the repository's expected LF-to-CRLF
  notices.

## Immediate Next Context

Resolve the two contract decisions above before, or explicitly alongside, Stage
6. The desktop shell still owns presentation paging/projection caches,
flattening/filtering/search, progress identity/autoscroll, database-paged
history, bounded/coalesced web event transport, task lifecycle, and the headed
WebView2 host. It must consume the reviewed service/workflow seams rather than
reimplementing sync, inventory, integrity, history, or dispatcher policy.
