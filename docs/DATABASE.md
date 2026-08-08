# Database Module

Status: schema bones, safe connection factories, the M0 ledger/repositories,
inventory reconciliation, bounded event-journal history, and M1's
ledger-v2/history-v4 coordinated reset boundary and semantic settings store are
implemented. General migrations, retention, and backup/protection workflows
remain later work.

## Purpose And Boundaries

`namisync.db` owns SQLite schemas, connection factories, recorder implementation,
read repositories, history observer/store, and later migrations. The main
ledger stores durable operational evidence; the history database stores an
independent activity audit. They have separate connections, versions,
retention, failure domains, and no cross-database foreign keys.

Live databases are local, never placed in a cloud-synced managed root.
Schema-versioned semantic defaults live in database-owned `settings.json`;
semantic settings used by a plan are snapshotted into that plan. Cosmetic UI
state is interface-owned and never shares this file.

## Implemented Foundation

`schema.py` creates a version-2 ledger and version-4 history schema. The ledger
freezes hosts, stable volumes plus mutable evidence, role-free locations,
soft-deletable mappings, current versus attested inventory state, mapping-scoped
correspondence, run/operation tokens, generic annotations, and nullable hardlink
group room. Database triggers reject correspondence whose rows do not belong to
the mapping's source and target locations.

`connections.py` enables foreign keys, WAL, and bounded busy timeout on writers;
read repositories open SQLite in `mode=ro` and enable `query_only`. Before
exposing a retained reader, both repository constructors validate the numeric
schema version and exact contract marker through that read-only connection;
every refusal closes the reader and leaves the database plus WAL/SHM/journal
sidecars byte-for-byte unchanged. Live paths can be validated against managed
roots before creation. `timestamps.py` is the single fixed-width aware-UTC
representation used by both schemas.

The M1 desktop shell (service facade) composes these per-file checks into one
read-only `validate_database_contracts()` preflight returning a
`fresh`/`ready`/`refused` pair state — including the exactly-one-present and
orphaned-sidecar refusals — applied across the GUI and CLI paths so history
cannot be initialized without the ledger. `M1_SHELL.md` Slice 1 step 8 owns that
contract; it is planned, not yet implemented.

`repositories.py` returns immutable inventory, run, and `MappingSnapshot`
values. Canonical path selections are queried in bounded 400-key chunks inside
one read transaction, so a concurrent commit cannot split one selection across
different database snapshots.

History version 4 creates a provisional `history_runs` row at the first durable
window and appends canonical reliable envelopes to `history_events`. Typed item
projection columns and dense one-based `item_order` support bounded item pages
and fixed-size conditional summary aggregates without decoding event JSON.
Free-form kind/reason values never create one summary object per group. Rolling
outcome counts,
state, phase, hashes, and watermarks advance in the same transaction as each
window. Terminal axes and bounded execute/verify phase summaries remain null
until finalization commits its tail and terminal marker atomically.
Commit time is sampled under serialized transaction ownership and remains
logically nondecreasing across wall-clock rollback, never preceding admission
or any newly committed event timestamp. Terminal phase names and failure type
names are capped at 256 UTF-8 bytes; phase and terminal error messages are
capped at 4,096 UTF-8 bytes in both observer validation and schema checks.
Summary reads and repeat finalization recompute the terminal hash from stored
axes and ordered phase rows before accepting finalized truth. They first
recompute the context hash from the fixed immutable run-context columns, so a
modified nullable or required context value is not returned as trusted truth.

`HistoryWindowPolicy` bounds one pending window to 256 reliable events and
1 MiB of canonical serialized data, rejects an individual event over 1 MiB,
and supplies the one-second age used by the dispatcher flush scheduler. Count,
byte, pause, age, clean-close, and finalization boundaries all commit; a crash
can lose only the last uncommitted window. A nonterminal committed row is
readable as `incomplete` after restart and is not classified as interrupted or
resumable without future durable custody.

The current schemas carry immutable whole-contract metadata: ledger
`contract_id=m1-ledger-xxh3-128-invalidation-v1` and history
`contract_id=m1-history-windowed-events-v1`. Opening ledger v1, history v1-v3,
or a transitional ledger-v3/history-v4 database with a missing/mismatched
marker raises the same actionable
`SchemaResetRequired` family without altering the old tables or version stamp.
During this pre-release window the user must close NamiSync and manually delete
both local database files before restarting. History version 3 cannot be
migrated into the reliable journal because it never stored state and phase
envelopes.
`reset_databases()` is an explicit
development/test helper that validates both exact paths before deleting their
database/WAL/SHM artifacts and recreates both current schemas; normal startup
never calls it. No general ordered migration, backup, retention, export/import,
or maintenance writer is claimed yet.

`settings.py` owns `SemanticSettingsStore`. A commit takes a deterministic
Windows named mutex, rereads the latest document while holding it, applies only
the supplied patch fields, and atomically replaces the UTF-8 JSON file. This
prevents two processes editing unrelated settings from reverting one another.
Reads require the exact integer schema discriminator and reject duplicate JSON
object keys rather than accepting boolean/integer equivalence or last-key-wins
ambiguity.
The store accepts user-facing `trash` and `additive`; hidden `mirror` is not a
persistable preference. Runtime composition defaults the path to
`settings.json` beside the selected ledger, so an explicit ledger override
also isolates its semantic defaults. The shared service exposes primitive
snapshot/patch views and never imports this package or leaks
`SemanticSettingsStore`, `SemanticSettings`, core enums, or `SyncOptions`.
Missing settings mean the schema defaults; malformed or wrong-schema settings
refuse planning before dispatcher submission.
Runtime refuses a settings path that aliases either database or lies inside a
managed root. Primitive view validation rejects non-boolean scalar values,
non-tuple/non-string filters, hidden deletion values, and wrong preservation
objects before the store can replace an existing or missing file.

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
- a paired verification-invalidation time/reason retaining metadata drift or
  hash mismatch without discarding the attested comparison baseline;
- metadata snapshot fields for attributes and creation time; ADS has no scan,
  inventory, or schema representation;
- physical presence, acknowledgement, reappearance, and unsupported state,
  independent of plan or interface view state;
- generic namespaced annotations with entity kind/id/key/value and uniqueness.

Successful byte-producing operation transactions return the persisted target
inventory row identity, target location, run scope token, and canonical path
key as one tuple. Idempotent replay returns the identical tuple. Compound
execute→verify reuses one run token/window and the same run-bound recorder for
conditional integrity writes; pause closes/reopens the connection without
ending the row, and terminal settlement fills `ended_at` once.

Drive letters are current mount/display data, never persisted identity. Label
drift is noted without rebind; a matching serial with a changed filesystem type
requires explicit rebind; simultaneous duplicate keys require explicit user
choice. A composite constraint/trigger must prevent a mapping correspondence
from referencing a target file in another location.

## Connection Rules

Every writable ledger connection enables foreign keys, WAL, bounded busy
timeout, and explicit transactions. The serialized writer spends one monotonic
contention budget across its local lock, SQLite busy waits, and retry sleeps;
the transaction body is not misclassified as contention time. Read repositories
use read-only connections where possible. A function named/read-scoped as
read-only may never be used for retention or other writes—the PoC made that
error and disabled pruning entirely.

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
observation from retained attested baseline and derive
unverified/verified/modified/mismatched state from the baseline, current stat,
last verified time, and sticky invalidation. History readers branch by activity
kind rather than rendering every activity as source-to-target. History list and
summary reads use a fixed query count and one primitive indexed fact row per
run; workflow-supplied predicates preserve workflow ownership of selection and
headline interpretation. Item and reliable-event reads use keyset pages with a
hard 256-row decoded/returned ceiling and a fixed watermark captured in the
same read transaction as the first page. Reliable sequences are sparse, so a
caller-supplied event watermark is an inclusive upper bound rather than a
promise that its sequence has a retained row. Event reads use one indexed
lookahead row for continuation and separately verify the run's official maximum
event sequence on every request. A fresh event traversal already ahead of that
maximum ends empty and must omit its watermark again when it later checks for
newly committed history. No public repository method materializes all detail
for a run.

## Integrity Constraints

- Canonical keys are computed in core, not SQLite `NOCASE`.
- Digests and their stat/provenance unit are written atomically.
- Retained content evidence may contradict current observation only with a
  paired durable invalidation marker; successful evidence replacement clears
  that marker atomically.
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
It runs only after a complete online scan of the declared scope. `FULL` uses an
all-location observed-key anti-join, exact `PATHS` updates only absent named
keys, and `SUBTREES` bounds the same anti-join to exact paths plus each root
equality and descendant range. The existing
`inventory_location_presence_idx(location_id, presence, rel_path_key)` supports
the default-binary literal range `root || '\'` through `root || ']'`; no
`LIKE`, collation change, schema migration, or ledger version bump is involved.
Missing rows retain evidence and may be acknowledged/restored/reappeared.
Tombstone pruning is a future explicit policy with impact review, not an
incidental scan cleanup.

Stale-inventory reads include rows with no evidence, no true verification time,
an age-expired verification, a durable invalidation, or a current/attested stat
contradiction. A matching later scan cannot erase a prior mismatch or drift;
only a guarded positive evidence transaction can make the row current again.

## Schema Evolution

Both databases start with a version stamp. The active pre-release boundary is
reset-and-refuse: no startup migration or partial schema repair runs. Before
real user evidence must survive a schema change, a dedicated ordered migration
module will take an atomic backup, check supported source versions, migrate
transactionally, verify integrity, and restore/refuse safely on failure.

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
independent history round-trip, old-schema refusal, coordinated development
reset, and settings concurrency are covered. Criteria for retention, general
migrations, backups, exports, and cloud-provider discovery remain future gates
rather than current implementation claims.

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
- Full/exact/subtree/offline inventory reconciliation obeys `INVENTORY.md`,
  seeks subtree descendants through the declared presence/key index, preserves
  hostile names literally, and scales beyond 33k rows without variable
  overflow.
- Large mapping/inventory selections use bounded query counts demonstrated by
  instrumentation benchmarks.
- Every history window is atomically visible or absent; its event/item
  watermark, chain hash, rolling counts, and typed rows advance together.
  Failed finalization preserves earlier windows and exposes the run only as
  incomplete.
- History integrity detail, sync operations, subject-only activities, and
  reliable lifecycle/phase events round-trip through bounded typed pages.
  Terminal axes, cancellation, `Disposition`, and compound phases appear only
  with the terminal payload marker. Integrity and headline are reconstructed
  from typed primitive aggregates through the same classifier as live results;
  they are not additional database columns.
- Summary reads use a fixed query count and no event JSON decoding. Item and
  event pages reject limits outside 1..256, concatenate without overlap, and
  retain a stable captured watermark while newer windows commit. Event pages
  decode at most the requested limit, use one indexed lookahead row across
  legitimate sequence gaps, and reject an official durable maximum that does
  not match its event rows.
- Ledger v1-v2, history v1-v3, and current-number transitional schemas lacking the
  exact final M1 contract marker are refused before writer/WAL/schema mutation
  with an actionable instruction to recreate both local databases.
- The explicit coordinated development reset recreates ledger v3/history v4;
  normal startup never deletes either database.
- Concurrent semantic-settings patches preserve unrelated fields because the
  read-modify-replace cycle is serialized across processes.
- Runtime/service settings reads expose the complete semantic snapshot, an
  all-optional patch preserves untouched keys, and an explicit ledger path
  resolves its sibling settings file unless `settings_path` is supplied.
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
