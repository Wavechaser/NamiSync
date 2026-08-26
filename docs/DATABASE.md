# Database Module

Status: schema bones, safe connection factories, the M0 ledger/repositories,
inventory reconciliation, bounded receipt-journal history, and M1's
ledger-v4/history-v6 data-epoch-6 reset boundary and semantic settings store are
implemented. General migrations, retention, and backup/protection workflows
remain later work.

## Active V4/V6 Persistence Boundary

Status: ledger-v4/history-v6 shapes are active from Stage 6 checkpoint 3.2;
remediation checkpoint 3R.14 advances the shared data epoch and ledger contract
id. This is a coordinated pre-release reset, not an in-place migration.

| Database | Schema | `data_epoch` | `contract_id` |
| --- | ---: | ---: | --- |
| ledger | 4 | 6 | `m1-ledger-v4-event-v5-evidence-v2` |
| history | 6 | 6 | `m1-history-v6-event-v5-recording-v1` |

Version, contract id, and epoch values are mandatory. Two absent main files
with no sidecars remain the only fresh state. Any old or mixed pair,
one-present pair, missing/wrong marker, incomplete/poisoned topology, or orphan
WAL/SHM/journal sidecar is refused by read-only validation before mutating
startup or CLI work. The refusal directs the user to close NamiSync and
archive or delete both database mains and all sidecars together; startup does
not migrate, repair, or delete them. A standalone read-only history command may
open one exact history-v6 database without creating or requiring its ledger
peer; it still validates the history role, version, contract id, epoch, and
complete topology through the shared nonmutating file preflight.

Epoch 6 separates the corrected identity-bearing hash preimages from epoch 5's
numeric file-index preimages. Recorder and plan hashes now project declared
contract fields explicitly and quote canonical `FileIndex128` text; ordinary
integers remain JSON numbers. SQLite column shapes and the history contract id
do not change. This fixes canonical consistency and latent portability risk,
not demonstrated Python integer-precision loss. Valid-Unicode identityless hash
bytes remain unchanged. A later boundary hardening requires Unicode scalar
strings/keys and strict UTF-8 without another epoch or schema change. JSON had
already distinguished surrogate escapes from literal backslashes; this is a
malformed-input/round-trip fix, not a demonstrated hash collision. Optional scan
warning detail is omitted at construction if malformed; its old captured
receipt consequently conflicts without mutation even when identityless. Valid
observations are still recorded. [CORE.md](CORE.md) and [RECORDER.md](RECORDER.md)
own that input policy and replay behavior; frozen old bytes remain immutable.

Both old epoch-5 databases, either mixed 5/6 direction, and epoch 6 carrying the
old ledger contract id are refused, including when the old markers are committed
only in WAL. Recreating the pair discards the active app inventory, baselines,
attestations, mappings, receipts, and audit history; archived files may be kept
for separate inspection but are not migrated into the new pair. It does not
delete or modify source files, target files, semantic settings, or sync trash.
A new scan can rebuild current observations, not the discarded historical
baselines, attestations, receipts, or audit trail.
No application startup or reader performs this destructive reset automatically.

Captured epoch-5 markers in `tests/assets/identity_epoch5_vectors.json` seed
synthetic old-pair fixtures against the unchanged ledger-v4/history-v6 shapes.
Repeated probes, pair admission, initializers, and repositories refuse both
old databases, each mixed 5/6 direction, and epoch 6 with the old ledger id.
WAL-only old markers refuse with or without source SHM; source main/WAL/SHM/
journal membership and bytes remain unchanged. Existing epoch-4 and journal
presence negatives remain independent controls, and fresh epoch-6 pairs reopen
with unchanged schema versions and history id. These tests never reset user data.

Ledger v4 stores complete file identities as canonical `FileIndex128` text and
strengthens pair, canonical-domain, and attestation checks. It does not add an
operation digest. The execution-evidence join and indexed recent-location
queries described below remain later checkpoint targets; process-local recent
ids remain outside the database.

At the active cutover, ledger numeric and native-identity storage follows
`DEFENSE.md` §1.3 and the mapped bridge decision without a database-local
domain or codec variant. `HISTORY.md` owns canonical event-envelope
persistence.

History v6 admits only its coordinated core-event version and adds a nullable,
all-or-complete review-limit terminal group. `HISTORY.md` owns its durable
observer/finalization consequences; `M1_BRIDGE.md` owns the exact shared shape.
Presentation-only omission state is never stored.

### Exact topology authority

Status: active from remediation checkpoint 3R.13, using the exact authority
prepared independently in 3R.12. Reader validation, initializer/repository
preflight, and pair admission all select it alongside the current markers.

`schema.py` compares the complete ordered `main.sqlite_schema` projection
`(type, name, tbl_name, sql)` with a private in-memory reference created from the
shipped role schema. SQLite's stored SQL is compared verbatim: there is no
case folding, whitespace removal, literal rewriting, or object-prefix filter.
Automatic indexes retain their null SQL. Physical root pages are excluded;
data and marker values remain outside this definition comparator.

Only these SQLite-owned table definitions are optional, at most once each:
`CREATE TABLE sqlite_stat1(tbl,idx,stat)` and
`CREATE TABLE sqlite_stat4(tbl,idx,neq,nlt,ndlt,sample)`. Their type, name, owner,
and SQL must match exactly. Undeclared statistics objects, duplicate rows, and
indexes/triggers attached to statistics tables are not exempt. The candidate
receives only a catalog read; DDL is restricted to the private reference, which
is always closed. The topology comparator is not a physical database-integrity
scan or a replacement for metadata-value validation.

### Nonmutating file admission

`contracts.py` owns the shared file preflight. Any lexical `-journal` entry,
including an empty file, directory, or dangling link, refuses before SQLite
access; an inaccessible entry is not absence. Pair admission checks both
journals before validating either role. Admission never guesses journal
hotness or performs rollback recovery on source artifacts.

With no WAL or SHM, the validator keeps the direct `mode=ro&immutable=1`
source read. Otherwise it copies only main and existing WAL bytes to an owned
`namisync-db-contract-*` temporary child of the database directory and validates
through ordinary read-only SQLite there.
SQLite sees committed WAL markers/topology and builds its own private SHM;
source SHM is drift evidence only, never copied or opened as recovery authority.
This also covers a missing source SHM. There is no SQLite backup call, source
checkpoint, custom WAL parser, or new database-size acceptance limit.

The private copy contains full database and WAL contents, not redacted schema
metadata. Placing it beside the database inherits the required local,
non-cloud-synced placement instead of trusting ambient `TEMP`/`TMP` selection;
this is not a new cloud-folder detector. The private-copy branch requires
permission to create and remove a child in that directory and scratch space
for main plus WAL plus SQLite's private SHM. Failure to create the child refuses
admission without falling back elsewhere; restore the required permissions or
use an appropriate local database location before retrying. The sidecar-free
immutable branch needs no scratch directory. Normal completion or refusal
removes the owned child; cleanup failures refuse admission, and a process crash
can leave private copies for explicit inspection/cleanup. There is no automatic
or broad directory scavenging. Validation never writes, recovers, or removes
source main/WAL/SHM/journal artifacts, but creating/removing the private child
can change its parent directory's entries and timestamps.

Each main/WAL/SHM observation binds regular-file identity, size, modification
time, and SHA-256 content. Stream reads are bounded by the observed length and
use at most 1 MiB per chunk. Copying and rechecks reject changed stamps before
reading or copying enlarged artifacts; final hashes also catch same-stamp
edits. Membership and journal checks bracket observation, and the pair gate
rechecks both roles after peer validation. Observed drift refuses; quiescent
ready/refusal/error fixtures preserve all source bytes, and injected-drift
fixtures retain only the external mutation. Private SQLite handles close before
temporary cleanup. One preflight-local cleanup guard covers source/copy handles,
the validation connection, and the temporary directory. Ordinary cleanup
errors annotate and preserve the primary error; an existing control
interruption wins, while a cleanup interruption outranks an ordinary primary
error. Outer cleanup is still attempted after inner failures. A cleanup
failure after successful validation refuses admission.

Existing-file initializers return after this preflight without an ordinary
source connection or `CREATE IF NOT EXISTS` repair. A pre-existing empty main
or orphan sidecar is not fresh. Repository constructors preflight first, then
open their ordinary reader, repeat exact contract validation, and close it on
refusal. The evidence is a point-in-time observation, not a source lease or an
atomic pair snapshot: mutation after the final guard and a repository's later
ordinary open remains outside the classifier's no-write guarantee.

Coordinated fresh creation uses a separate private schema-creation path only
after every reserved main/WAL/SHM/journal entry still matches its ownership lease
and is an empty regular file. The existing handle-bound rollback remains in
force. Standalone fresh `initialize_*` calls do not acquire those leases; their
absence-to-writer-open race is not an exclusive cross-process creation boundary.

### Runtime reader ownership and admission diagnostics

`LocalWorkflowRuntime` owns at most one lazy ledger reader and one lazy history
reader for its four inventory/mapping and four history presentation-read methods.
Separate role locks serialize complete queries and view materialization, including
first construction. Every newly opened handle still receives the full file
preflight and post-open contract validation. An owned reader is not a detached
path/stamp validation cache: it stays bound to its admitted database until retired
or the runtime closes. Missing history keeps its empty-list/unknown-run behavior
while no reader is owned, without caching absence. Replacing or resetting database
files requires closing the application and opening a new runtime.

Successful requests do not retain a transaction between calls. Existing multi-statement
history and selected-inventory reads keep their per-request transactions; ordinary
single-statement inventory reads remain autocommit. Later requests therefore see
later committed updates without reopening the reader. Any query or projection
exception retires that reader; a successful close permits a fully admitted retry.
A failed retirement close retains the handle and quiesces the runtime. Ordinary
cleanup errors annotate the original error, an existing control interruption wins,
and a new cleanup interruption outranks an ordinary primary error. Runtime close
quiesces before waiting for active reads, clears only successfully closed owners,
and keeps failed or not-yet-closed owners for an explicit close retry. A queued
read cannot reopen a reader, and audit setup cannot recreate a history writer,
after quiescing starts. The service's dispatcher shutdown timeout is not a new
reader-query or reader-close deadline. Two owned reader handles is not a bound
on native SQLite cache memory.

This change amortizes admission, not query work or first-open validation. Let
`M`, `W`, and `S` denote source main, WAL, and SHM lengths, with absent sidecars
counted as zero. The current preflight's Python streams read/hash `2M` logical
bytes without sidecars; the private-copy branch reads/hashes `3M + 3W + 2S` and
writes `M + W` copied bytes plus SQLite's private SHM. Pair admission adds a final
`M + W + S` recheck per role. These are source-derived diagnostics, excluding
SQLite page reads, small EOF probes, cache effects, and filesystem allocation;
they are not measured physical I/O, latency limits, or database-size walls.
Planning correspondence, location binding, integrity selection, pair checks,
recorders, initializers, and standalone repositories retain their existing full
admission paths.

Standalone-integrity candidate reads are a distinct bounded repository path.
Fresh full and exact-path reads apply directory and mode eligibility in SQL;
stale scope unions exact completed rows by row identity; and saved resume reads
only its exact row ids and restores their original order. Every branch uses one
explicit read snapshot, streams raw rows into typed projections, and refuses at
the first eligible row beyond the core-owned candidate count. Chunking cannot
publish a torn or partial population, and SQLite's numeric affinity cannot make
a noncanonical saved spelling satisfy exact missing-row validation. The direct
exact-path reader may retain one normalized lookahead key so SQL mode
eligibility, rather than raw request cardinality, decides that boundary; the
workflow request itself admits at most 120,000 raw selected paths. The frozen
model must charge that one repository-only transient. The retained-graph byte
axis remains part of the checkpoint-4 model rather than a database estimate.

The retained fixture is `test_repeated_runtime_reads_admit_once_per_owned_handle`
in `tests/test_runtime_readers.py`. Its admission-count matrix
uses the shipped role DDL with two SQLite page sizes (1,024 and 8,192 bytes), an
empty ledger or a five-event history run, and initially absent sidecars or a live
WAL writer with a benign committed `user_version` change. It executes each role's
four read methods for three cycles, asserting one admission/open after 4, 8, and
12 requests, one close on owner shutdown, and another full admission on a new
runtime and on a standalone repository. It does not measure actual database byte
scaling. A service summary-plus-page traversal and live-writer fixtures separately
exercise public reachability and visibility of later commits. Counts are exact
per-case observations, never averaged; the committed tests are the rerunnable
artifact, with no empirical timing or memory baseline. Rerun after changes to
runtime ownership, repository transactions, schema/connection factories, file
admission, or SQLite/Python behavior. The I/O algebra must also be re-derived when
the admission stream/copy sequence changes. Quantitative classification remains
owned by `DEFENSE.md` §7.

`tests/test_database_contracts.py` separately exercises both roles with a
redirected ambient temp directory, exact private main/WAL bytes, absent copied
SHM, failed child creation without fallback, cleanup faults, and an immutable
no-scratch control. These functional placement and no-mutation witnesses do not
measure physical disk allocation, cleanup latency, or a maximum database size.

### Atomic execution-evidence read

Status: accepted for the later execution-review checkpoint; not active in
checkpoint 3.2.

The execution-evidence repository resolves one retained execution identity and
a bounded operation window in one SQLite read transaction. It joins committed
operation identity to current target inventory evidence through the canonical
target key, batches keys, treats duplicate eligible operations as ambiguity,
and never substitutes an internal row id for the textual run token.

It returns the evidence needed for the bridge-owned recorded-copy,
already-verified, unrecorded, superseded, and not-applicable classification;
current-state evidence cannot silently become execution evidence. Later task
failure does not revoke an independently committed item receipt.

Manual exact handoff requires a fresh coherent snapshot, repeats the repository
read before verifier attachment, and retains the original execution scope as
conditional authority. Recording degradation outside an item does not erase
coherent item evidence; explicit settlement divergence blocks the handoff.

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

`schema.py` creates a version-4 ledger and version-6 history schema. The ledger
freezes hosts, stable volumes plus mutable evidence, role-free locations,
soft-deletable mappings, current versus attested inventory state, mapping-scoped
correspondence, run/operation tokens, generic annotations, and nullable hardlink
group room. Database triggers reject correspondence whose rows do not belong to
the mapping's source and target locations.

`connections.py` enables foreign keys, WAL, and bounded busy timeout on writers;
read repositories open SQLite in `mode=ro` and enable `query_only`. Both
repository constructors use the shared file preflight above before opening
that reader, then repeat the exact current contract check before exposing it.
Live database paths can be validated against
managed roots before creation; that containment resolver converts long managed
roots only at the native I/O boundary and compares ordinary logical spellings.
This is not a claim that SQLite database files themselves may use overlong
paths. `timestamps.py` is the single fixed-width aware-UTC
representation used by both schemas.

The M1 desktop shell service composes these per-file checks into one
read-only `validate_database_contracts()` preflight returning a
`fresh`/`ready`/`refused` pair state — including the exactly-one-present and
orphaned-sidecar refusals — enforced by the CLI mutation paths and ready for
the Slice 1 product host to consume before window creation, so history cannot
be initialized without the ledger. Validation uses the shared immutable or
private-WAL path above, never source SHM recovery authority.
Fresh creation is a separate, serialized workflow operation: it
publishes ledger then history after reserving every main and sidecar cleanup
target through a Windows ownership lease. Failure cleanup derives a new delete
handle from the retained reservation with `ReOpenFile` and requests
exact-object disposition; a displaced foreign pathname is retained rather than
removed through a check/use race. Rollback covers ordinary exceptions,
`KeyboardInterrupt`, and `SystemExit`; handles release stepwise and an
incomplete cleanup carries the coordinated reset direction. It never invokes
the destructive development reset. A crash-shaped one-main pair, an orphan
sidecar, an empty/unversioned
file, or a role/version-marker mismatch is refused with the coordinated
manual-reset direction and no mutation.

`repositories.py` returns immutable inventory, run, and `MappingSnapshot`
values. Canonical path, file-identity, and canonical positive-decimal row-ID
selections are queried in bounded 400-subject chunks inside one read
transaction, so a concurrent commit cannot split one selection across different
database snapshots. Row-ID lookups are location-scoped, deduplicate in
first-requested order, and omit malformed or missing identifiers rather than
broadening the query.

History version 6 creates a provisional `history_runs` row at the first durable
window and appends disposition-bound reliable receipts to `history_events`.
Canonical and exact-duplicate rows retain their envelopes; a supported
oversized event retains only bounded metadata, reason, and its original payload
hash; an oversized result item additionally retains fixed-size identity and
semantic hashes. Typed canonical-item projection columns are derived by the
writer from retained envelope JSON, become immutable with the receipt row, and
are checked against decoded envelopes on detail reads. The strict composite-key event
table is `WITHOUT ROWID`; official writers require recursive triggers, while
insert/update/delete and run-finality guards make committed receipts and runs
append-only. Dense one-based `item_order` supports bounded item pages and fixed-size
conditional summary aggregates without decoding event JSON. Exact semantic
duplicates advance sequence and the receipt chain without allocating item
order or outcome counts; changed item identity remains corruption even when
the first occurrence was rejected for size. Free-form kind/reason values never
create one summary object per group. Receipt hashes bind retained event
metadata, disposition, item hashes/link/reason, and item order. Rolling outcome
and duplicate/rejection counts, state, phase, hashes, and watermarks advance in
the same transaction as each window. Terminal axes and bounded execute/verify
phase summaries remain null until finalization commits its tail and terminal
marker atomically.
Each identity has one indexed recorded or unlinked-rejected representative.
Later exact oversized copies remain rejected and increment the rejection count,
but link to that representative; a bulk bounded lookup never scans the linked
history for that identity.
Commit time is sampled under serialized transaction ownership and remains
logically nondecreasing across wall-clock rollback, never preceding admission
or any newly committed event timestamp. Terminal phase names, failure type
names, phase errors, and terminal failure messages are each capped at 1,024
UTF-8 bytes in both observer validation and schema checks.
Each window also stores a prefix-projection hash over context/receipt-chain
hashes, lifecycle timestamps/state/phase, watermarks, and every rolling count.
Summary reads validate it for incomplete and finalized runs. Repeat
finalization and finalized reads additionally recompute the terminal hash from
that prefix, stored terminal axes, and ordered phase rows before accepting
finalized truth. A modified context, projection, counter, or ordering value is
therefore not returned as trusted truth.
Indexed physical event/item tails are compared with the official watermarks in
summary/page reads, observer reopen, and writer admission, so an out-of-band
tail cannot affect classification or reopen a committed prefix.

`HistoryWindowPolicy` bounds one pending window to 256 reliable events and
1 MiB of canonical serialized data. Core event v5 refuses a reliable envelope
over that same ceiling before sequence or queue mutation; the history observer
retains its hash-only rejection path as defensive policy for directly injected
or deliberately stricter-policy tests. The policy also supplies the one-second
age used by the dispatcher flush scheduler. Count,
byte, pause, age, clean-close, and finalization boundaries all commit; a crash
can lose only the last uncommitted window. A nonterminal committed row is
readable as `incomplete` after restart and is not classified as interrupted or
resumable without future durable custody.

The current schemas carry exact whole-contract metadata: ledger
`contract_id=m1-ledger-v4-event-v5-evidence-v2`, history
`contract_id=m1-history-v6-event-v5-recording-v1`, and shared `data_epoch=6`.
Opening ledger v1-v3, history v1-v5, or a current database with a
missing/mismatched marker raises the same actionable
`SchemaResetRequired` family without altering the old tables or version stamp.
During this pre-release window the user must close NamiSync and manually delete
or archive both local database files and their sidecars before restarting.
There is no migration into this coordinated event-v5/evidence epoch: older
pairs either lack required facts or retain the superseded identity-bearing hash
convention. Advancing the epoch does not reinterpret their stored receipts.
`reset_databases()` is an explicit
development/test helper that validates both exact paths before deleting their
database/WAL/SHM/journal artifacts and recreates both current schemas; normal startup
never calls it. The reset is intentionally destructive and non-transactional:
all NamiSync and SQLite handles must already be closed, and a locked sidecar can
make a later delete fail after an earlier artifact was removed. The caller must
clear the lock and rerun the coordinated reset/recreation; this helper is not a
user-data recovery guarantee. No general ordered migration, backup, retention,
export/import, or maintenance writer is claimed yet.

`settings.py` owns `SemanticSettingsStore`. A commit takes a deterministic
Windows named mutex, rereads the latest document while holding it, applies only
the supplied patch fields, flushes the replacement payload, and atomically
replaces the UTF-8 JSON file. This prevents two processes editing unrelated
settings from reverting one another. The settings store does not claim
parent-directory write-through across sudden power loss; preferences are not
part of the audit ledger's durability contract.
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

At the active checkpoint-3 reset, file-index columns and repository binds use
canonical `FileIndex128` text rather than SQLite numeric affinity. The exact
identity domain and native-source rule remain owned by `M1_BRIDGE.md` and
`DEFENSE.md` §1.3.

Successful byte-producing operation transactions return the persisted target
inventory row identity, target location, run scope token, and canonical path
key as one tuple. Idempotent replay returns the identical tuple. Compound
execute→verify reuses one run token/window and the same run-bound recorder for
conditional integrity writes; pause closes/reopens the connection without
ending the row, and terminal settlement fills `ended_at` once.

Official writers keep observed and attested file-identity fields paired and
clear attested-only fields when no content evidence exists. Ledger v4 encodes
identity-pair, canonical `FileIndex128`, invalidation, and current-versus-
attested consistency rules as raw-SQL checks, and repositories defensively
reject corrupt identity text. Attested creation time remains legitimately
optional.

Drive letters are current mount/display data, never persisted identity. Label
drift is noted without rebind; a matching serial with a changed filesystem type
requires explicit rebind; simultaneous duplicate keys require explicit user
choice. A composite constraint/trigger must prevent a mapping correspondence
from referencing a target file in another location.

## Connection Rules

Every writable ledger connection enables foreign keys, WAL, bounded busy
timeout, and explicit transactions. The serialized writer spends one monotonic
contention budget across its local lock, SQLite busy waits, and retry sleeps;
the transaction body is not misclassified as contention time. Only SQLite
primary result codes `SQLITE_BUSY` and `SQLITE_LOCKED`, including their extended
forms after primary-code masking, are retryable; exception message text never
controls contention handling. Read repositories use read-only connections where
possible. A function named/read-scoped as read-only may never be used for
retention or other writes—the PoC made that error and disabled pruning entirely.

First-time schema creation still relies on the connection's bounded SQLite busy
timeout rather than an application-level database-pair startup mutex or retry
loop. Concurrent process startup can therefore refuse after that bound; a
persistent multi-process service must add a pair-scoped initialization gate and
two-process regression before claiming stronger startup liveness.

The serialized recorder owns normal writes. Schema creation/migration and
dedicated maintenance are the only other write owners and do not run inside
ordinary sync module code.

## Repository Rules

Repositories return typed immutable snapshots for planner, inventory, verifier,
history views, and mapping guidance. Reads are batched by canonical key; no
one-query-per-path loop for large selections. Query functions never refresh
state as a side effect.

The planning mapping reader derives its complete query scope from the two
current file scans. It reads correspondence only for current target path keys,
then retains only current source identities and a current target identity or the
existing nullable target-identity evidence. Source and target disqualification
queries cover only identities present in those scans while still counting every
matching inventory alias and retained multi-link observation. Mapping lookup,
all 400-key/identity batches, and disqualification share one SQLite snapshot;
the bounded result is restored to canonical source-key/target-key order before
planning. Irrelevant historical location rows are therefore never materialized
by planning. The general mapping snapshot reader remains available for explicit
mapping inspection.

Inventory reads distinguish current observation from retained attested baseline
and derive unverified/verified/modified/mismatched state from the baseline,
current stat, last verified time, and sticky invalidation. History readers
branch by activity kind rather than rendering every activity as source-to-target. History list and
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

Retention and backup/protection workflows are unimplemented future requirements.
Detail retention must use a writable connection and canonical time comparison,
preserve summaries when pruning detail, and remain idempotent. Backup snapshots
must pass integrity check, and rotation must never delete the newest sole good
backup.

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
