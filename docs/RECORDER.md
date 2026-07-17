# Recorder Module

Status: draft contract. Priority: M0 sync recording; M1 integrity/import
recording. DR-15 must resolve how recording failure contributes to session
status.

## Purpose

Recorder is the only write path into the main ledger. Executor, inventory
reconciliation, verifier, baseline, hash import, rebind, annotations, and later
maintenance issue typed commands; none executes SQL directly. Recorder
serializes in-process writes, applies conditional evidence rules, batches within
a bounded durability window, and fails visibly.

History is not recorder output. It independently observes session events and
uses a separate database.

## Command Contract

Recorder commands carry complete immutable evidence and idempotency keys. At
minimum the protocol covers:

- run/session start and filesystem-result window;
- confirmed copy/update/move/trash/delete/mkdir/no-op correspondence;
- complete/scoped inventory reconciliation and missing/reappearance state;
- conditional baseline, verify, rebaseline, and external hash import;
- mapping/location/rebind and soft-delete state;
- namespaced annotations;
- `flush()` at explicit durability boundaries.

Calls return typed applied/no-op/stale/conflict results or raise a typed
recording error. They never return ambiguous booleans and never swallow
SQLite/OS errors.

## Ordering And Truth

User-data mutation or observation happens before its corresponding ledger
command. Recorder commits statements that were true at a known observation
time; if the world has since drifted, conditional writes affect zero rows. The
ledger may lag after a crash, but it must not lead reality.

Before executor performs a destructive operation, recorder flushes all prior
earned evidence. Pause-drain and session terminal force flush. M0 may implement
each command transactionally with a no-op batching abstraction, but the real
protocol and flush points exist from day one.

## Conditional Evidence Primitive

Hash/baseline/verification/import writes are gated on location, row id,
canonical path, present state, expected size/mtime/identity, current hash policy,
and run/op token. No match means `stale`, not an insert/update against whatever
now occupies the path.

The same rule protects no-op correspondence refresh: both source and target
must still match the plan snapshot before identity, last-seen, or mapping state
advances. Hashed inventory baseline stats are never overwritten by ordinary scan
observation.

## Serialized Writer And Transactions

One in-process writer owns a writable ledger connection or serialized command
queue. Parallel disjoint-volume sessions may submit concurrently but commit in a
defined order. Cross-process connections use WAL, foreign keys, bounded busy
timeout, and bounded retry. Long CPU/path matching work happens before opening a
write transaction; inputs are pre-indexed by canonical key.

Transactions are operation/batch scoped, not multi-hour activity scoped. One
late failure cannot erase hours of earned verification evidence. A failed
operation does not roll back independent earlier committed operations.

## Idempotency

Run and operation tokens have database uniqueness constraints and command-level
no-op handling. Repeating a command after an uncertain response returns the
already-applied result without duplicating rows, annotations, or run counts.
Idempotency does not treat different evidence under the same token as valid; it
raises a token-conflict corruption signal.

Move rekeying clears/reconciles a colliding retained-missing row at the intended
same location before insert/update, and updates the old row state on succeeded,
skipped, and failed outcomes according to actual observation. It never resolves
a collision by rolling back the entire run silently.

## Recording Failure Semantics

DR-15 must define the aggregate status. Recorder always returns/raises the
recording failure to the workflow. The already successful filesystem result is
preserved verbatim and interfaces disclose “files changed; ledger behind” rather
than “copy failed.” Recovery re-inventories/reconciles; it never rolls back true
filesystem work merely to make the ledger tidy.

## Expectations

- Core supplies commands/evidence/results and one UTC clock.
- Executor/verifier/import never share the recorder's SQLite connection or issue
  SQL.
- Repositories are read-only and cannot smuggle writes through a helper.
- Workflow aggregates filesystem and recording outcomes.
- Database schema enforces location/mapping integrity and idempotency.
- History failure/success is independent of recorder transaction outcome.

## Latent Features

Bounded batching adds operation-count/time thresholds behind the same calls.
Cross-host ledger merge, migration, backup, undo, and maintenance use typed
commands or dedicated app-artifact workflows, not ad hoc SQL from interfaces.
Hardlink group recording remains nullable until preservation semantics exist.

## PoC Hardening

- Wiring recorder into workflows prevents the built-but-unused ledger.
- Separate filesystem/recording result prevents inverted trust reporting.
- Actual start/end timestamps prevent post-hoc identical run windows.
- Conditional writes fix stale hash backfill and no-op evidence refresh.
- Bounded transactions fix multi-hour verify lock/loss.
- Serialized writer and longer bounded retry fix disjoint-run contention.
- Batched missing marking fixes SQLite variable overflow.
- Colliding missing-row handling fixes whole-run rollback/data loss.
- Pre-indexed snapshots fix O(operations × scan) lock holds.
- Paired no-op correspondence preserves later move evidence.
- Guarded path normalization errors cannot roll back unrelated earned records.

## Acceptance Criteria

- Static/import tests prove no production ledger write occurs outside recorder
  and schema/migration ownership.
- Every mutation command is preceded by a successful matching filesystem result
  in integration traces; fault injection cannot commit future intent.
- Conditional writes under every drift dimension affect zero rows and return
  `stale` without altering prior evidence.
- Repeating identical run/op commands is a no-op; token reuse with different
  payload is rejected.
- Two disjoint-volume sessions record completely through one serialized writer
  under stress; cross-process contention retries within bound and surfaces final
  failure.
- A late verifier failure preserves earlier committed per-file evidence.
- Flush occurs before each destructive operation, on pause drain, and before
  terminal delivery; crash loses at most the declared batch window.
- Recorder failure preserves the original filesystem `ExecResult` and produces
  the finalized DR-15 ledger-behind outcome.
- Complete inventory over 33k entries and large path selections use bounded
  batches with no SQL parameter overflow.
- Move onto a retained missing row reconciles that row and keeps unrelated run
  writes; location mismatch is rejected by schema.
- No-op recording requires matching source/target snapshots and persists source
  identity correspondence needed for later rename detection.
- Copy-attested digest stores correct provenance and never advances true
  verification time.
- One shared UTC/host runtime produces identical representations across ledger
  and history boundaries.

