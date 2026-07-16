# NamiSync History and Audit Store

## Current scope

History schema version 2 is an independent append-oriented SQLite database.
Version 1 development history is not migrated: close NamiSync and remove only
`history.db`, `history.db-wal`, and `history.db-shm` before first v2 use. This
never changes the main ledger or any filesystem root.

The acknowledgement/reappearance work remains part of the same unreleased v2
cut. Development v2 files created before this round must be reset because no
same-version migration is supplied.

History always uses foreign keys, WAL, canonical UTC timestamps, and a bounded
busy timeout. It has no foreign keys to the main ledger; a failed history write
does not roll back valid filesystem or inventory work.

## Envelope and typed details

`history_runs` stores a unique run token, activity kind (`sync`, `baseline`,
`verify`, or `import_hashes`), executing host, final status, activity window,
recorded time, processed bytes, activity error, bookkeeping error, and detail
state. It exposes a composite `(id, activity_kind)` key.

`history_run_locations` stores immutable normalized snapshots: source and
target for sync, or subject for one-location activity. Typed summaries use the
same composite foreign key:

- `history_sync_summaries` and ordered `history_sync_operations`;
- `history_integrity_summaries` and retained integrity detail in
  `history_integrity_issues`;
- `history_import_summaries`.

A baseline count is distinct from a verified count. Null-hash reads during a
verify attempt increment only the baseline count. Import summaries distinguish
accepted, already-known, conflicting, skipped, error, and canceled entries.
Integrity summaries also retain scope (`all`, `selected`, or post-execution)
and the number of reappeared rows encountered. Reappearance detail records the
path even when a stable match clears the main-ledger `reappeared_at` marker;
ordinary mismatch/modified/error detail remains unchanged.

Every explicit sync, baseline, verify, and import attempt is history-worthy,
including successful no-op and canceled attempts. Repeating a run token is
idempotent. Ordinary scans are inventory observations and create no history run.

History entry reads dispatch by activity kind. Sync entries expose their ordered
operations; baseline and verify entries expose their retained integrity issues,
including outcome, path, digest evidence when available, and error detail. The
CLI and History dialog show a one-location entry's subject directory rather
than synthetic source/target values.

## Retention

Summary retention defaults to 365 days. Retained operation or integrity issue
detail defaults to the newest five runs per activity/location scope and 90 days;
pruning changes `detail_state` to `pruned` while keeping the envelope and
summary. The historical narrative remains independent from main-ledger
missing-row pruning. Startup and the History dialog's Apply retention action
open `history.db` writable, so their retention sweep can actually remove
expired envelopes and detail. CLI integrity commands accept
`--history-database` for isolated scripted audit stores.
