# Recorder Module

Status: M0 sync recording, ledger setup, inventory reconciliation, and the
shared conditional integrity write are implemented. Hash import and maintenance
recording remain later work.

## Purpose

Recorder is the only write path into the main ledger. Executor, inventory
reconciliation, verifier, baseline, hash import, rebind, annotations, and later
maintenance issue typed commands; none executes SQL directly. Recorder
serializes in-process writes, applies conditional evidence rules, batches within
a bounded durability window, and fails visibly.

History is not recorder output. It independently observes session events and
uses a separate database.

## Implemented Foundation

`namisync.db.recorder.LedgerRecorder` owns one serialized writable connection.
It records hosts, volume evidence, role-free locations, mappings, actual run
windows, inventory observations, sync outcomes, and conditional integrity
evidence. `begin_sync_run()` validates an execution run's mapping, physical
volumes, plan, selection, and token, then returns a run-bound
`SyncRunRecorder` implementing the executor's narrow recorder protocol. This
keeps run and plan context out of every per-operation call without making
operation ids globally unique across reruns.

M0 uses eager operation-scoped transactions behind the final batching
interface. Every successful call is already durable, and `flush()` is therefore
a boundary-compatible no-op rather than a missing seam. One re-entrant lock
serializes threads; WAL, SQLite busy timeout, and bounded retry handle another
process. Exhausted contention raises `RecordingBusyError`.

All sync operation kinds record only after the executor reports matching
filesystem success. Copy/update evidence is bound to the published target stat,
tagged `copy`, and never advances `last_verified_at`. Paired no-ops require both
live stats to match the reviewed snapshots. Move recording validates the prior
row before carrying its evidence forward and transactionally reconciles a
retained-missing destination row. A pure move preserves that row's content hash,
provenance, and `last_verified_at` — a same-volume rename keeps size, mtime, and
identity — so a later verify verifies against carried-forward evidence instead of
re-baselining; a move of a never-hashed file simply carries no hash. Move-update
overwrites content and therefore records fresh `copy` evidence.

Workflow exclusions do not call the main-ledger recorder: blocked intent and
deferred quarantine/withholding are audit-history facts, not durable filesystem
evidence. Selected no-ops still run their live guards and call `record_noop`, so
even an otherwise degraded safe-subset run refreshes valid correspondence for
future complete-scan move detection.

Inventory reconciliation batches observations and uses a temporary key table
for complete missing sweeps, so a 33k+ location never becomes a giant parameter
list. The integrity primitive gates row, location, canonical path, present
state, scope token, current stat, and full expected attestation. Evidence,
`last_verified_at`, and `reappeared_at` change in one transaction or not at all.

## Command Contract

Recorder commands carry complete immutable evidence and idempotency keys. Copy
and update commands receive `Attestation(ContentEvidence, published_target_stat)`;
the source's post-read stat remains separate drift evidence and is never stored
as target identity. At minimum the protocol covers:

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

Recorder always returns/raises the recording failure to the workflow. The
already successful filesystem result and terminal `SessionState` are preserved
verbatim; `OperationResult.recording` becomes `RecordingStatus.DEGRADED` and
interfaces disclose “files changed; ledger behind” rather than “copy failed.”
Recovery re-inventories/reconciles; it never rolls back true filesystem work
merely to make the ledger tidy.

## Expectations

- Core supplies commands/evidence/results and one UTC clock.
- Executor/verifier/import never share the recorder's SQLite connection or issue
  SQL.
- Repositories are read-only and cannot smuggle writes through a helper.
- Workflow aggregates filesystem, ledger-recording, and independent audit
  outcomes; recorder controls only the ledger axis.
- Database schema enforces location/mapping integrity and idempotency.
- History failure/success is independent of recorder transaction outcome.

## Latent Features

Bounded batching adds operation-count/time thresholds behind the same calls.
Cross-host ledger merge, migration, backup, undo, and maintenance use typed
commands or dedicated app-artifact workflows, not ad hoc SQL from interfaces.
Hardlink group recording remains nullable until preservation semantics exist.

## PoC Hardening

- Wiring recorder into workflows prevents the built-but-unused ledger.
- Axis-separated filesystem/ledger/audit result prevents inverted trust
  reporting while keeping history outside recorder.
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

The M0-owned criteria below are covered by focused schema, sync, inventory,
integrity, concurrency, repository, and verifier-recorder integration tests.
Workflow result aggregation and executor flush placement are verified by their
own layer tests; bounded multi-operation batching remains latent because M0
commits every command eagerly.

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
  `RecordingStatus.DEGRADED` without changing the filesystem terminal.
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
