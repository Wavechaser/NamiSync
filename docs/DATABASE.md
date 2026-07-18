# Database Module

Status: schema bones, safe connection factories, the M0 ledger/repositories,
inventory reconciliation, and minimal sync history are implemented. Migrations,
retention, backup/protection workflows, and richer history remain later work.

## Purpose And Boundaries

`namisync.db` owns SQLite schemas, connection factories, recorder implementation,
read repositories, history observer/store, and later migrations. The main
ledger stores durable operational evidence; the history database stores an
independent activity audit. They have separate connections, versions,
retention, failure domains, and no cross-database foreign keys.

Live databases are local, never placed in a cloud-synced managed root. Settings
live in a separate local settings file; semantic settings used by a plan are
snapshotted into that plan.

## Implemented Foundation

`schema.py` creates independent version-1 ledger and history schemas. The ledger
freezes hosts, stable volumes plus mutable evidence, role-free locations,
soft-deletable mappings, current versus attested inventory state, mapping-scoped
correspondence, run/operation tokens, generic annotations, and nullable hardlink
group room. Database triggers reject correspondence whose rows do not belong to
the mapping's source and target locations.

`connections.py` enables foreign keys, WAL, and bounded busy timeout on writers;
read repositories open SQLite in `mode=ro` and enable `query_only`. Live paths
can be validated against managed roots before creation. `timestamps.py` is the
single fixed-width aware-UTC representation used by both schemas.

`repositories.py` returns immutable inventory, run, and `MappingSnapshot`
values. Canonical path selections are queried in bounded 400-key chunks, and
mapping correspondence is returned with stable source/target volume evidence
and hardlink/duplicate-identity disqualification. Reads never refresh state.

The present migration policy is explicit refusal on a schema-version mismatch.
Reset remains an external/manual operation; no ordered migration, backup,
retention, export/import, or maintenance writer is claimed yet.

## Main Ledger Shape

The initial schema reserves the expensive identity/evidence bones:

- schema metadata/version;
- hosts as observation/run provenance;
- volumes keyed by `VolumeId(serial, fs_type)`, with mutable label/mount
  `VolumeEvidence` stored only as corroboration;
- role-free locations keyed by physical volume plus volume-relative root path;
- inventory rows keyed by location plus canonical relative path;
- optional file identity and nullable hardlink-group room;
- mappings linking distinct source/target locations with soft `deleted_at`;
- mapping-scoped correspondence constrained to rows in the mapping's locations;
- run/op idempotency tokens and actual UTC run window;
- digest algorithm/value, `ContentEvidence`, attested subject stat, provenance,
  observed/hash/verified times kept semantically distinct;
- metadata snapshot fields for attributes and creation time; ADS has no scan,
  inventory, or schema representation;
- presence, acknowledgement, exclusion, reappearance, and unsupported state;
- generic namespaced annotations with entity kind/id/key/value and uniqueness.

Drive letters are current mount/display data, never persisted identity. Label
drift is noted without rebind; a matching serial with a changed filesystem type
requires explicit rebind; simultaneous duplicate keys require explicit user
choice. A composite constraint/trigger must prevent a mapping correspondence
from referencing a target file in another location.

## Connection Rules

Every writable ledger connection enables foreign keys, WAL, bounded busy
timeout, and explicit transactions. Read repositories use read-only connections
where possible. A function named/read-scoped as read-only may never be used for
retention or other writes—the PoC made that error and disabled pruning entirely.

The serialized recorder owns normal writes. Schema creation/migration and
dedicated maintenance are the only other write owners and do not run inside
ordinary sync module code.

## Repository Rules

Repositories return typed immutable snapshots for planner, inventory, verifier,
history views, and mapping guidance. Reads are batched by canonical key; no
one-query-per-path loop for large selections. Query functions never refresh
state as a side effect.

Mapping snapshots include correspondence from paired no-ops, missing rows,
identity ambiguity, and location ids. Inventory reads distinguish current
observation from retained attested baseline. History readers branch by activity
kind rather than rendering every activity as source-to-target.

## Integrity Constraints

- Canonical keys are computed in core, not SQLite `NOCASE`.
- Digests and their stat/provenance unit are written atomically.
- Mapping source and target locations are distinct and non-nested validation is
  performed before insertion.
- Soft-deleted mappings cannot be duplicated silently; matching create offers
  restore.
- Run/op tokens are unique.
- Annotation keys are namespaced and unique per entity/key; orphan/cascade
  policy is explicit despite generic entity references.
- Timestamps enter normalized aware UTC form and are compared as parsed time or
  canonical fixed representation, never mixed arbitrary ISO text.

## Inventory And Missing Retention

Missing marking uses temp tables or bounded batches, not a giant `NOT IN` list.
It runs only after a complete online full-location scan. Missing rows retain
evidence and may be acknowledged/restored/reappeared. Tombstone pruning is a
future explicit policy with impact review, not an incidental scan cleanup.

## Schema Evolution

Both databases start with a version stamp. Before real evidence must survive a
schema change, a dedicated ordered migration module takes an atomic backup,
checks supported source versions, migrates transactionally, verifies integrity,
and restores/refuses safely on failure. Early reset-and-refuse behavior is
acceptable only before user evidence exists and must be explicit.

Legacy import/merge is separate from normal startup migration. It never guesses
volume/location correspondence.

## Data Protection

Quick-check and backup run as ordinary dispatcher maintenance sessions. Use the
SQLite backup API or equivalent consistent snapshot to a temp destination,
fsync/flush according to platform guarantee, then atomically publish the dated
backup. Rotation deletes only recognized backup artifacts after a successful
new backup and according to reviewed count/age policy. Optional second-volume
backup requires its own custody.

Export/import validate versions and never overwrite the live database without a
verified backup/atomic replacement path. Trash retention is filesystem-domain
maintenance but uses ledger/history evidence and capacity planning; undo creates
an ordinary reviewed plan.

## Expectations Of Other Modules

- Core supplies canonical keys, ids, evidence, commands, UTC clock protocol, and
  schema-neutral domain types.
- Scanner/planner/executor/verifier never open ledger connections directly.
- Workflows request typed repository snapshots and submit writes through
  recorder.
- Dispatcher writes only its separate session store behind `SessionStore`; it
  never imports this package under the import law.
- Interfaces access typed application/workflow reads, never raw SQL or database
  paths hidden from test overrides.
- History has an independent connection/schema/failure domain and no foreign key
  to the ledger.

## PoC Hardening

The schema/connection/repository contract covers role coupling, unrelated
location foreign keys, unbounded missing tombstones, short busy timeout, false
copy verification time, unexpected-error audit loss, SQL parameter overflow,
move/missing unique collision, readonly retention, baseline stat overwrite,
unread integrity detail, stale skipped-move rows, O(n²) transaction work,
casefold over-merge, lost path guards, missing paired-noop evidence, excessive
round trips, and duplicated time/host formatting.

## Acceptance Criteria

Fresh-schema, pragma, read-only, cross-location trigger, canonical path,
volume/rebind, 33k reconciliation, bounded repository query, WAL concurrency,
and independent history round-trip cases are covered in the M0 suite. Criteria
for retention, migrations, backups, exports, and cloud-provider discovery remain
future gates rather than current implementation claims.

- Fresh schemas contain every freeze field, version stamp, index, uniqueness,
  and foreign-key/trigger constraint required above.
- `PRAGMA foreign_keys`, WAL, and busy timeout are verified on every connection
  type; readonly connections reject writes by construction.
- Schema rejects cross-location mapping correspondence despite valid row ids.
- Windows path-key corpus stores NTFS-distinct names separately and ordinary
  case/separator variants as one key.
- Volume mount-letter/label changes preserve location identity; a changed
  filesystem type requires rebind, and simultaneous duplicate identities require
  explicit user choice.
- Complete/scoped/offline inventory reconciliation obeys `INVENTORY.md` and
  scales beyond 33k rows without variable overflow.
- Large mapping/inventory selections use bounded query counts demonstrated by
  instrumentation benchmarks.
- History integrity detail, sync operations, and subject-only activities all
  round-trip through typed repository reads.
- History run envelopes round-trip filesystem status, independent
  recording/audit axes, and `Disposition` without deriving them from detail
  count or text.
- Retention uses a writable connection, canonical time comparison, preserves
  summaries when pruning detail, and is idempotent.
- Concurrent recorder/repository/history access does not lose committed evidence
  or return partial transactions.
- Migration fault injection at backup, each step, validation, and publish leaves
  either the old valid database or new valid database, never a half migration.
- Backup snapshots pass integrity check and rotation never deletes the newest
  sole good backup.
- Databases/settings/backups are refused inside managed/cloud-synced roots unless
  an explicit safe external location policy says otherwise.
