# Recorder Module

Status: sync recording, ledger setup, inventory reconciliation, the shared
conditional integrity write, atomic copy-identity returns, and one logical
recorder window across optional linked verification are implemented.
Maintenance recording remains unrealized.

## Recording Truth (Event v5 Active)

The exact result vocabulary is owned by [core contracts](CORE.md). Each
recorder call produces one typed,
operation-local truth result. A committed receipt is final and idempotent; an
identical byte-producing replay returns the same complete
`RecordedCopyIdentity`. Executor now retains a failing call as that operation's
typed recording reason. Executor retains final-flush and post-settlement
divergence at task scope; workflow retains recording-open, finish, and close
issues there. Storage failure cannot degrade a different operation or revoke an
earlier committed transaction.

The identity relation remains exact: `operations.run_id` refers to `runs.id`,
while `RecordedCopyIdentity.scope_token` is that run's textual `run_token`.
Location id and canonical target key come from the same transaction as the
receipt and evidence. Recorder adds no operation-digest column.

Executor and workflow own settlement attribution and manual post-copy policy.
Recorder only supplies typed storage outcomes and conditional writes against
the original scope, rechecking row, location, canonical path, present state,
scope, current stat, attestation, and invalidation at the point of use.

## Purpose

Recorder is the only write path into the main ledger. Executor, inventory
reconciliation, verifier, baseline, rebind, and annotations issue typed
commands; maintenance would use the same seam when implemented. None executes
SQL directly. Recorder serializes in-process writes, applies conditional
evidence rules, batches within a bounded durability window, and fails visibly.

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

The workflow opens or finishes that run from a frozen `RecordingSpec` carrying
the already-admitted plan, selection, run id, and optional commitment by
identity. `LocalWorkflowRuntime` passes this projection to its production
`_LedgerRunRecording`, which retains the spec rather than the mutable
`ExecutionSet`; status, publication evidence, byte progress, and recording
attribution remain workflow/executor state. This custody change does not alter
ledger commands, run tokens, selection digests, callback order, settlement, or
schema.

Volume, location, and inventory entry points reconstruct the exact typed
command before any transaction. Volume identity/evidence use the core text and
path ceilings, location paths are freshly validated and canonicalized, and an
inventory command retains exact `ScanResult` and child-tuple transfer checks
alongside its scalar validation. Complete scan-graph validation belongs to
initial `ScanResult` construction. Recorder hash projection keeps the exact
outer transfer and per-record, warning, and scope projectors, so its necessary
serialization checks remain independent of command reconstruction.

M0 uses eager operation-scoped transactions behind the final batching
interface. Every successful call is already durable, and `flush()` is therefore
a boundary-compatible no-op rather than a missing seam. One re-entrant lock
serializes threads; WAL, SQLite busy timeout, and bounded retry handle another
process. Exhausted contention raises `RecordingBusyError`.

COPY/UPDATE/MOVE_UPDATE recording returns a complete
`RecordedCopyIdentity(row_id, location_id, scope_token, rel_path_key)` from the
same transaction that stores the copy evidence. Replaying the identical
operation token reconstructs the same tuple; conflicting token reuse fails.
There is no partial/fake identity. If that transaction fails after bytes
publish, executor retains rowless evidence only beside that operation's
`record-write-failed` reason and derives a degraded aggregate.

All sync operation kinds record only after the executor reports matching
filesystem success. Copy/update evidence is bound to the published target stat,
tagged `copy`, and never advances `last_verified_at`. Paired no-ops require both
live stats to match the reviewed snapshots. Move recording validates the prior
row before carrying its evidence forward and transactionally reconciles a
retained-missing destination row. A pure move preserves that row's content hash,
provenance, `last_verified_at`, and any existing invalidation because a
same-volume rename keeps size, mtime, and identity. A later verify therefore
compares against carried-forward evidence instead of re-baselining; a move of a
never-hashed file simply carries no hash. Move-update
overwrites content and therefore records fresh `copy` evidence. Recase recording
uses the same row/correspondence reconciliation while requiring the explicit
`recase` operation kind; it updates only stored target spelling and observed
stat, preserving content evidence with the same file identity.

Idempotency payload hashes preserve valid-Unicode bytes and use strict UTF-8;
malformed required evidence is refused before a command transaction, not escaped
into an identity. Optional `ScanWarning.detail` is checked at construction:
malformed Unicode becomes the existing empty detail, while code, path, valid
detail, and scan observations remain intact. The hash covers this constructed
command without a recorder-specific fallback. An old receipt containing the
previously tolerated malformed detail conflicts without mutation on replay;
valid-Unicode receipts are unchanged by this policy, so no new epoch/reset is
required.

Workflow exclusions do not call the main-ledger recorder: blocked intent and
deferred quarantine/withholding are audit-history facts, not durable filesystem
evidence. Selected no-ops still run their live guards and call `record_noop`, so
even an otherwise degraded safe-subset run refreshes valid correspondence for
future complete-scan move detection.

Inventory reconciliation retains the fixed 400-row observation and unsupported
`executemany` groups. Exact `PATHS` and `SUBTREES` absent-key updates use
`connections.QUERY_SUBJECT_BATCH_SIZE` (400), with at most the batch size plus
four statement parameters, then branch explicitly on
`FULL`, exact `PATHS`, and recursive/mixed `SUBTREES` after completeness is
known. Full and subtree branches use a temporary observed-key table; subtree
missing inference is additionally bounded to exact keys plus each root equality
and the indexed literal range `>= root || '\' AND < root || ']'`. It marks
absent prior `present` and `unsupported` rows, never already-`missing` or
out-of-scope rows, and never uses wildcard-sensitive `LIKE`. Full sweeps still
scale past 33k rows without a giant parameter list.

The configured root itself is owned by the `locations` row and is not duplicated
as an empty-path inventory child; descendant observation upserts therefore
reject an empty relative path. Complete FULL/SUBTREES reconciliation uses a
connection-local observed-key scratch table, clearing it before use and after a
successful batch; rollback restores a failed use and connection close drops the
table. Duplicate keys in a malformed complete FULL/SUBTREES scan fail and roll
back instead of being silently ignored and authorizing false missing inference;
complete PATHS input is set-deduplicated, and the native scanner reports case
collisions as incomplete before this boundary.

Observation upserts retain attestation but atomically set a sticky
`metadata-drift` invalidation when current kind/size/mtime or known identity no
longer matches its subject; missing and unsupported transitions do the same.
An existing `hash-mismatch` is never downgraded by later scan metadata. Fresh
copy/baseline/rebaseline/verified evidence clears the marker only while its full
conditional guard still matches.

The integrity primitives gate row, location, canonical path, present state,
scope token, current stat, full expected attestation, and expected invalidation.
Positive evidence, `last_verified_at`, invalidation clearing, and
`reappeared_at` change in one transaction or not at all. Negative
metadata-drift/hash-mismatch recording is separately idempotent; hash mismatch
dominates later metadata drift until a positive evidence transaction clears it.

## Command Contract

Recorder commands carry complete immutable evidence and idempotency keys. Copy
and update commands receive `Attestation(ContentEvidence, published_target_stat)`;
the source's post-read stat remains separate drift evidence and is never stored
as target identity. At minimum the protocol covers:

- run/session start and filesystem-result window;
- confirmed copy/update/move/move-update/recase/trash/delete/mkdir/no-op
  correspondence;
- full, exact-path, and recursive-subtree inventory reconciliation plus
  missing/reappearance state;
- conditional baseline, verify, and rebaseline;
- conditional durable verification invalidation for missing/modified/mismatched
  reads;
- mapping/location/rebind and soft-delete state;
- namespaced annotations;
- `flush()` at explicit durability boundaries.

Calls return typed applied/no-op/stale/conflict results or raise a typed
recording error. They never return ambiguous booleans and never swallow
SQLite/OS errors.

Corrupt joined-location context and a malformed paired no-op without its
required source path raise typed recording errors and leave the command
transaction unchanged.

## Ordering And Truth

User-data mutation or observation happens before its corresponding ledger
command. Recorder commits statements that were true at a known observation
time; if the world has since drifted, conditional writes affect zero rows. The
ledger may lag after a crash, but it must not lead reality.

Before any operation reaches its final destructive source/destination guards,
recorder flushes all prior earned evidence. A resumed MOVE_UPDATE whose old
path is already in owned trash performs no new mutation and needs no redundant
pre-mutation flush. Pause-drain and session terminal force flush. M0 may
implement each command transactionally with a no-op batching abstraction, but
the real protocol and flush points exist from day one.

For an opt-in compound run, `LedgerRecorder`/`SyncRunRecorder` remains the one
outer writer and logical run window from execute through verify. Pause may
close the connection and reopen the same unfinished token idempotently; it does
not finish the run. Verification reuses that same run-bound recorder for
conditional integrity writes. Complete, mismatch, modified, cancel,
preflight-incomplete, ordinary `Exception`, and finish-failure paths attempt one
terminal finish; a finish error degrades recording without rewriting filesystem
or integrity truth.

## Conditional Evidence Primitive

Hash/baseline/verification/invalidation/import writes are gated on location,
row id, canonical path, present state, expected size/mtime/identity, current
attestation/invalidation, and run/op token. No match means `stale`, not an
insert/update against whatever now occupies the path.

The same rule protects no-op correspondence refresh: both source and target
must still match the plan snapshot before identity, last-seen, or mapping state
advances. Hashed inventory baseline stats are never overwritten by ordinary scan
observation.

## Serialized Writer And Transactions

One in-process writer owns a writable ledger connection or serialized command
queue. Parallel disjoint-volume sessions may submit concurrently but commit in a
defined order. Cross-process connections use WAL, foreign keys, bounded busy
timeout, and bounded retry. One monotonic contention deadline covers acquisition
of the in-process writer lock, every SQLite busy-handler allowance, and retry
sleep; each attempt caps `PRAGMA busy_timeout` to the remaining budget and no
positive-budget attempt begins after expiry. A zero retry budget still permits
one immediate uncontended attempt. The operation body begins only after the
write transaction is acquired and is deliberately outside this contention
budget. Long CPU/path matching work happens before opening a write transaction;
inputs are pre-indexed by canonical key.

Retry classification uses SQLite result codes, not exception prose. Only
primary `SQLITE_BUSY` and `SQLITE_LOCKED` are contention, with extended codes
masked to their primary value; another operational error containing words such
as "busy" or "locked" fails immediately as a recording error.

Transactions are operation/batch scoped, not multi-hour activity scoped. One
late failure cannot erase hours of earned verification evidence. A failed
operation does not roll back independent earlier committed operations.

## Idempotency

Run and operation tokens have database uniqueness constraints and command-level
no-op handling. Repeating a command after an uncertain response returns the
already-applied result without duplicating rows, annotations, or run counts.
Idempotency does not treat different evidence under the same token as valid; it
raises a token-conflict corruption signal.
Inventory receipt hashes include both exact paths and recursive subtree roots,
so reusing one location/scope token with a different recursive scope conflicts
instead of returning a false replay `NOOP`.

Move rekeying clears/reconciles a colliding retained-missing row at the intended
same location before insert/update, and updates the old row state on succeeded,
skipped, and failed outcomes according to actual observation. It never resolves
a collision by rolling back the entire run silently.

## Recording Failure Semantics

Recorder always returns/raises the recording failure to the workflow. The
already successful filesystem result and terminal `SessionState` are preserved
verbatim. Internal continuation state retains sparse item reasons and ordered
task issues; exact event v5 exposes operation-local recording facts while its
item-free terminal summary carries the degraded-item count and ordered task
issues. Recovery re-inventories/reconciles; it never rolls back true filesystem
work merely to make the ledger tidy.

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
