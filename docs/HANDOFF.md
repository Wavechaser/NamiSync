# NamiSync Session Handoff

Date: 2026-07-18

## Session Outcome

Implemented the M0 backend walking skeleton from core contracts through the
independent ledger/history boundary. The shared checkout now contains the
dispatcher, scanner, planner, preflight, executor, verifier, recorder,
repositories, and history observer with their focused acceptance suites. The
remaining M0 shipping slice is workflow/composition and the CLI surface.

All implementation remains uncommitted in the shared working tree.

## Dispatcher And Core Session Plane

- Added `core/evidence.py`, `core/session.py`, and `core/events.py`: validated
  evidence, the frozen lifecycle/transition table, axis-separated terminal
  results, opaque session records, the sole terminal-producing runner, typed
  event bodies, gap-free envelopes, delivery classes, and the version-1 M0
  event codec.
- Added `dispatcher/contracts.py`, `store.py`, `custody.py`, `event_bus.py`, and
  `dispatcher.py`, with public exports in `dispatcher/__init__.py`.
- Admission is domain-blind: workflow adapters prepare opaque bytes plus
  generic resources and reopen their own continuation snapshot on resume.
- Scheduling permits disjoint-resource concurrency while preserving FIFO on
  every contended resource, including a multi-resource waiter blocked on a
  different resource. Resume returns to the back of admission.
- Windows custody uses deterministic global named mutexes, sorted acquisition,
  cooperative cancellation, partial-acquisition cleanup, and abandoned-holder
  recovery. The portable provider supplies the same process-local contract.
- Pause and cancellation share one checkpoint, release custody before visible
  pause/terminal state, and retain reliable item outcomes across
  pause/resume/cancel or failure. Workflow code cannot emit `Terminal`.
- Event fan-out coalesces only progress, provides bounded replay, current state,
  exact first-missed `Gap` notices and subscriber ejection, and a bounded
  admission-time audit observer whose failure/timeout degrades only the audit
  axis. Terminal publication waits for the observer finalization decision.
- M0 intentionally uses `InMemorySessionStore`; restart persistence,
  reconciliation, leases/heartbeats, network-share custody, and configurable
  replay/conflation remain M2 work.

## Scanner, Planner, And Preflight

- Added `core/pathing.py`, `models.py`, `planning.py`, and `preflight.py`, plus
  isolated `modules/scanner.py`, `planner.py`, and `preflight.py`.
- Path/core contracts provide canonical Windows relative validation,
  one-codepoint case keys, long-path handling, immutable roots, volume and
  capability profiles, stats, scans, plans, and observation/verdict types.
- Scanner supports full and selected-path scans; exact owned-artifact handling;
  placeholder/reparse/permission/error classification; cancellation during
  enumeration; and explicit completeness, cycle, case, hardlink, and identity
  warnings without losing denial evidence.
- Planner is pure and byte-stable, with symmetric filters, explicit mkdir
  chains, metadata diffs, correspondence-qualified move/move-update detection,
  policy removals, dependency cleanup, typed blockers, and hardlink-aware
  capacity accounting. Malformed cross-volume identities are rejected.
- Observation converts ordinary filesystem/configuration read failures to
  typed evidence. Pure preflight exhaustively checks scan/root/volume/selection
  validity, nested roots, dependencies, direct and parent drift, settings,
  capacity/reclaimable exact temps, trash, containment, and representation.
  Workflow commitment remains outside preflight.

## Executor

- Added `core/execution.py`, `modules/executor.py`, and
  `tests/test_executor.py`.
- Execution contracts include validated run ids, mutable `ExecutionSet`
  continuation, typed reasons/decisions, copy digests, and injected
  filesystem/copy/clock/failure/recorder protocols.
- The executor implements copy, update, move, move-update, mkdir, trash, guarded
  delete, and no-op with exact owned temps, atomic conditional publication,
  hardlink-or-copy update backups, final evidence guards, root/reparse/trash
  safety, deferred directory metadata, bounded retries, throttled progress,
  cleanup on cancellation/pause/exception, and separately reported recording
  degradation.
- Dispatcher owns custody and terminal emission; workflows own fresh
  observe/preflight and commitment validation.

## Verifier

- Added `core/integrity.py`, `modules/verifier.py`,
  `tests/modules/test_verifier.py`, and
  `tests/test_verifier_recorder_integration.py`.
- Baseline, verify, and explicit rebaseline provide typed per-file outcomes,
  lossless pause/cancel continuation, cache-honest same-handle evidence, and
  conditional recorder commands.
- The native Windows unbuffered path is exercised directly, including alignment
  behavior and a regression proving readers are permitted while concurrent
  write/delete sharing is denied so the hashed path cannot be replaced.
- The real verifier/recorder integration proves atomic digest plus
  `reappeared_at` rollback and idempotent retry. Inventory selection and
  workflow/interface composition remain to land.

## Recorder, Database, Repositories, And History

- Added `core/recording.py`; `db/connections.py`, `timestamps.py`, `schema.py`,
  `writer.py`, `recorder.py`, `repositories.py`, and `history.py`; database test
  fixtures and focused schema/recorder/repository/history/concurrency/boundary
  suites.
- Ledger and history use independent versioned SQLite schemas, WAL, foreign
  keys, busy timeouts, fixed UTC encoding, read-only/query-only readers, and a
  serialized `BEGIN IMMEDIATE` writer with bounded busy failure.
- `LedgerRecorder` is the sole main-ledger writer. It implements setup,
  run-bound idempotent operation receipts, transactional recording for every M0
  executor operation, 400-row inventory reconciliation, retained-missing/move
  handling, offline and incomplete-scan semantics, and fully conditional
  integrity evidence with atomic reappearance clearing.
- Repositories expose immutable typed reads, bounded selection chunks, and
  mapping correspondence snapshots. The independent history observer stores
  reliable preterminal envelopes, axis-separated summaries, ordered typed
  details, and idempotent/conflict-checked finalization without importing the
  dispatcher.

## Documentation

Updated the authoritative component documents for implemented behavior:
`CORE.md`, `DISPATCHER.md`, `SCANNER.md`, `PLANNER.md`, `PREFLIGHT.md`,
`EXECUTOR.md`, `VERIFIER.md`, `RECORDER.md`, `DATABASE.md`, `INVENTORY.md`, and
`HISTORY.md`. Matching implementation/status passages were updated in
`FEATURES.md`, `ARCHITECTURE.md`, and `README.md`. `WORKFLOWS.md` was read and
followed but remains a composition contract, not an implemented workflow.

## Verification

- Final shared suite: **229 passed in 5.10s**.
- Dispatcher/core focused suite: **52 passed**.
- Scanner/planner/preflight/path focused suites: **79 passed** (15 scanner,
  22 planner, 29 preflight, 13 shared path/core).
- Executor focused suite: **37 passed**.
- Verifier focused suite: **33 passed** (32 module tests plus one real
  verifier/recorder integration).
- Persistence plus verifier-integration focused selection: **28 passed**.
- Import Linter: **7 contracts kept, 0 broken** (34 files, 89 dependencies).
- `git diff --check`: clean; Git reports only expected LF-to-CRLF notices.
- Real Windows coverage includes subprocess named-mutex holder termination and
  abandoned recovery, unbuffered verifier handle/share behavior, atomic
  verifier/recorder rollback/retry, and cross-process SQLite contention.

## Next Work

1. Implement the workflow/composition layer that joins scan, plan, repeated
   observe/preflight, commitment, execution, recording, verification, and the
   dispatcher without weakening the import law.
2. Add the M0 CLI `sync` review/commit/execute flow and `history` browsing over
   those workflows. The current `workflows` and `interfaces` packages remain
   skeletons.
3. Keep deferred scopes honest: USN/network scanning, non-everything planning
   scopes and content-hash/ingest policies, continue-with-skips, ADS and
   restartable/parallel/background-throttled execution, richer integrity/history
   detail and hash import, retention/migrations/backups, and M2 durable dispatcher
   queue/reconciliation are not implemented by this slice.
