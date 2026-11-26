# Database Module

Status: schema bones, safe connection factories, ledger/repositories, inventory
reconciliation, bounded receipt-journal history, the ledger-v5/history-v9
schemas with forward migration from NamiSync 0.1.0, the maintenance claim, and
the semantic settings store are implemented, as are check, backup, restore and
backup rotation ([Data Protection](#data-protection)). Retention remains
unrealized.

## Persistence Versions

Status: ledger v5 and history v9 are current (M2-A3, 2026-11-25). Each
database is judged on its own as current, older and supported, newer, or
refused; [Schema Evolution](#schema-evolution) owns the rules and the migrator.

| Database | Schema | `schema_metadata` rows |
| --- | ---: | --- |
| ledger | 5 | `role`, `schema_version`, `format.event`, `format.evidence`, `format.identity`, `format.numeric`, `format.path-key`, `format.preimage`, `format.recording`, `instance_id` |
| history | 9 | `role`, `schema_version`, `format.event`, `format.numeric`, `format.preimage`, `format.recording` |

`LEDGER_FORMATS` and `HISTORY_FORMATS` in `schema.py` declare the embedded
formats; each row holds that format's `FORMAT_VERSIONS` value. Ledger v5 also
holds the `ledger_lineage` table, added to the unreleased schema in place by
M2-A4, amended in place for a `migrated-released` kind and amended back
without it ([Ledger instance and ids](#ledger-instance-and-ids)). Two absent main
files with no sidecars remain the only fresh state; a `-wal` or `-shm` beside
its main is normal. One main present, current or older and supported, with the
other absent and no sidecar of it, is `incomplete`: only an explicit call
creates the missing database ([One database missing](#one-database-missing)).
A journal or an orphan sidecar is
refused by read-only validation before mutating startup or CLI work, with
non-destructive inspection or retry guidance, as are access failures and
observed activity. Older supported and newer databases are typed admission
refusals without reset guidance, as is a database at the other role's path
(the two paths look swapped) or one whose `role` this version does not know,
and a ledger backup copied into place by hand (`ledger-is-backup`).
If SQLite reports corruption or an invalid database file during cold admission,
the refusal identifies the affected role and directs the user to preserve both
databases and their sidecars for inspection, to run `namisync check`, and,
given a backup made by `namisync backup`, to restore it
([Data Protection](#data-protection)).
Only a stable confirmed unsupported
database — a pre-release version or contract id, missing or
mismatched metadata, an incomplete or poisoned topology, an empty or
markerless SQLite file — directs the user to close NamiSync and
archive or delete that database main and its sidecars. Both databases are
named only when both are unsupported; beside a current or supported older
peer, the direction names only the unsupported database and its path, says to
keep the peer, and says that the next start creates a new one
([Migration](#migration)). Startup never
repairs or deletes artifacts. A standalone read-only history command may open
one current history database without creating or requiring its ledger peer; it
still validates role, version, formats and complete topology through the shared
nonmutating file preflight, and it refuses an older history with direction to
start NamiSync once.

Pre-release epochs are history. Epoch 6 separated the corrected
identity-bearing hash preimages from epoch 5's numeric file-index preimages
under the former ledger-v4/history-v6 pair; those facts and their frozen
receipt fixtures remain historical evidence. History v7 removed the redundant
duplicate-link UPDATE guard, and history v8 changed the SQL row-limit
constraint so refusals record 150,000 exactly while still recognizing 120,000.
NamiSync 0.1.0 released ledger v4 (`m1-ledger-v4-event-v5-evidence-v2`) and
history v8 (`m1-history-v8-event-v5-recording-v1`) at data epoch 8; that pair
migrates. Epoch-5 and epoch-6 pairs, history v7, and mixed directions with
them stay refused with the reset direction. Recreating a refused pair discards
its inventory, baselines, attestations, mappings, receipts and audit history;
archived files may be kept for separate inspection. It does not delete or
modify source files, target files, semantic settings, or sync trash. No
application startup or reader performs this destructive reset automatically.

Refusal tests write old markers onto copies of the released fixture: captured
epoch-5 markers on both roles or one role beside a current peer, the epoch-6
ledger's prior contract id, epoch-7 history, and old markers committed only in
WAL with or without source SHM; source main/WAL/SHM/journal membership and
bytes stay unchanged. Because `data_epoch` is not read, a ledger of the
released shape and contract id with any epoch row classifies as older and
supported (`test_released_data_epoch_is_not_read`). Fresh pairs reopen only
with the exact current metadata. These tests never reset user data.

The ledger (since v4) stores complete file identities as canonical `FileIndex128` text and
strengthens pair, canonical-domain, and attestation checks. It does not add an
operation digest. Bounded recent-location readback uses the existing schema;
new recent-query indexes and the execution-evidence join remain unrealized.
Process-local command and task ids remain outside the ledger.

Ledger numeric and native-identity storage follows
`DEFENSE.md` §1.3 and the mapped bridge decision without a database-local
domain or codec variant. `HISTORY.md` owns canonical event-envelope
persistence.

History (since v8) admits only its coordinated core-event version and retains a nullable,
all-or-complete review-limit terminal group. `HISTORY.md` owns its durable
observer/finalization consequences; `namisync/core/events.py` owns the exact shared internal shape.
Presentation-only omission state is never stored. The duplicate-link INSERT
guard remains the writer admission for canonical receipt links. The
unconditional append-only UPDATE guard rejects every history-event rewrite,
including a duplicate-link rewrite, so schema v7 removes only the redundant
duplicate-link UPDATE guard.

### Exact topology authority

Status: active. Reader validation, initializer/repository preflight, and pair
admission all select the exact topology authority alongside the current
markers.

`schema.py` compares the complete ordered `main.sqlite_schema` projection
`(type, name, tbl_name, sql)` with a private in-memory reference created from the
shipped role schema. SQLite's stored SQL is compared verbatim: there is no
case folding, whitespace removal, literal rewriting, or object-prefix filter.
Automatic indexes retain their null SQL. Physical root pages are excluded;
data and marker values remain outside this definition comparator. Fresh
creation, the reference and migration all build objects from the same shipped
statement list (`_LEDGER_STATEMENTS`, `_HISTORY_STATEMENTS`), so one authority
holds. A released v0.1.0 database is compared with its released topology
instead: the SHA-256 of the same projection (`_topology_digest`), frozen in
`schema.py` and checked against the fixture.

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
rechecks both roles after peer validation. Cold admission retries only observed
artifact drift, at most three validation attempts with a 10 ms pause between
attempts. Pair admission retries the whole classification and both cold roles;
standalone first reads use the same policy without nested retries. This bounds
attempt count, not total time spent reading database-sized snapshots. The typed
file-contract probe remains a single-attempt observation. A cleanup failure prevents
retry, preserving its primary error and cleanup evidence. Quiescent
ready/refusal/error fixtures preserve all source bytes, and injected-drift
fixtures retain only the external mutation. Private SQLite handles close before
temporary cleanup. One preflight-local cleanup guard covers source/copy handles,
the validation connection, and the temporary directory. Ordinary cleanup
errors annotate and preserve the primary error; an existing control
interruption wins, while a cleanup interruption outranks an ordinary primary
error. Outer cleanup is still attempted after inner failures. A cleanup
failure after successful validation refuses admission.

A schema failure is provisional until its source evidence passes the same final
stability check. Persistent drift refuses with busy/retry guidance. Missing,
inaccessible, journal-bearing, or otherwise unreadable artifacts refuse with
non-destructive inspection/access guidance; none of these observations proves
incompatibility or warrants resetting the pair. Only a stable confirmed schema
mismatch carries the existing reset direction. SQLite `SQLITE_CORRUPT` and
`SQLITE_NOTADB` produce a `database-damaged` pair refusal with preservation
guidance. An older supported database (`DatabaseMigrationRequired`) and a
newer one (`DatabaseNewerVersion`) are typed refusals with their own
direction. CLI history reports typed admission refusals with exit code 3;
unrelated later history-read failures retain exit code 4. Retries never replay a
task or execute database initialization, recovery, or other effects.

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

Cold file admission above remains byte-preserving. A runtime adopts a database
role only when it first needs a SQLite reader or recorder. Adoption owns one
read-only SQLite connection for that role until runtime close; a standalone
history read does not require or create a ledger peer. Thereafter role
admission validates the exact schema in a SQLite read transaction on the owned
database, rather than requiring mutable main/WAL/SHM bytes to remain stationary.
Ordinary SQLite sidecar bookkeeping and committed recording are permitted in
this live phase. Planning a fresh pair and explicit cold classification do not
create databases or adopt connections merely to report readiness. Pair checks
combine live validation of owned roles with cold preflight of unopened roles.

Live ownership is not a cached pathname verdict: opens require the same role
and main-file identity, no journal entry, and current SQL contract validation.
Windows SQLite handles pin their main files against replacement; the explicit
identity check also refuses observed replacement. Reader/writer connections
opened through `DatabaseConnectionOwner` are validated on their own SQLite
snapshot. HistoryStore's internal `_load_existing` and `_load_event_receipt`
readers connect directly and do not repeat schema admission. Placement checks
still precede recording. Standalone constructors without a runtime owner retain the cold
file preflight. Runtime shutdown releases these ownership connections after
its readers and history writer; callers must finish task recording before close.

`LocalWorkflowRuntime` owns at most one lazy ledger reader and one lazy history
reader for its four inventory/mapping and four history presentation-read methods.
Separate role locks serialize complete queries and view materialization, including
first construction. Every newly opened handle receives live-owner admission
and post-open contract validation. An owned reader is not a detached
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
reader-query or reader-close deadline. The two query readers and two role-owner
connections are not a bound on native SQLite cache memory.

This change amortizes admission, not query work or first-open validation. Let
`M`, `W`, and `S` denote source main, WAL, and SHM lengths, with absent sidecars
counted as zero. The current preflight's Python streams read/hash `2M` logical
bytes without sidecars; the private-copy branch reads/hashes `3M + 3W + 2S` and
writes `M + W` copied bytes plus SQLite's private SHM. Pair admission adds a final
`M + W + S` recheck per role. These are source-derived diagnostics, excluding
SQLite page reads, small EOF probes, cache effects, and filesystem allocation;
they are not measured physical I/O, latency limits, or database-size walls.
These formulas apply to cold preflight. Runtime planning correspondence,
location binding, integrity selection, pair checks and recorders share the
role-owner admission above. Public initializers and standalone repositories
without a runtime owner retain full cold preflight.

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
workflow request itself admits at most 150,000 raw selected paths. Database
reads refuse before publishing a partial population. Repository input and
output gates use the core population ceiling and excess comparison.
Inventory and integrity own their exact error/fact outcomes; raw occurrences are checked before
normalization or deduplication, and returned rows before first-excess typed
projection.

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

Status: implemented. This section owns database evidence use;
[PRESENTATION.md](PRESENTATION.md) owns the cross-layer execution-review contract.

The execution-evidence repository admits at most 256 raw operation subjects
before normalization or SQL. An empty request is inert. A nonempty request
resolves the textual run token, the requested operation tokens, and the
canonical target keys in one SQLite read transaction with at most three data
queries. It uses the run's target location, never substitutes an internal row
id for the textual run token, and never scans the complete run or inventory for
one window.

It returns raw run, receipt, and current-inventory facts. The workflow owns the
recorded-copy, already-verified, unrecorded, superseded, and not-applicable
classification; adapters only forward that result. Current-state evidence
cannot silently become execution evidence. Later task failure does not revoke
an independently committed item receipt.

Verify copied uses the ordinary selected-path scan and integrity
reader. The former complete-population manual-handoff reader is retired; the
bounded atomic execution-evidence reader remains unchanged. An inventory scan
can supersede execution-relative evidence even when bytes are unchanged. Current
ledger verification is separate from evidence attributed to that original run.

## Purpose And Boundaries

`namisync.db` owns SQLite schemas, connection factories, recorder implementation,
read repositories, history observer/store, the maintenance claim, schema
migration (`migration.py`), and check, backup, restore and backup rotation
(`maintenance.py`). The main
ledger stores durable operational evidence; the history database stores an
independent activity audit. They have separate connections, versions,
retention, failure domains, and no cross-database foreign keys.

Use `sqlite3` directly, without an ORM; enable WAL for the main database.
Live databases are local, never placed in cloud-synced folders. Record durable
filesystem state only after the corresponding operation succeeds.
Schema-versioned semantic defaults live in database-owned `settings.json`;
semantic settings used by a plan are snapshotted into that plan. Cosmetic UI
state is interface-owned and never shares this file.

## Implemented Foundation

`schema.py` creates a version-5 ledger, with a random `instance_id` and
`AUTOINCREMENT` ids for locations, mappings and inventory, and a version-9
history schema. The ledger
freezes hosts, stable volumes plus mutable evidence, role-free locations,
soft-deletable mappings, current versus attested inventory state, mapping-scoped
correspondence, run/operation tokens, generic annotations, restore lineage, and
nullable hardlink group room. Database triggers reject correspondence whose
rows do not belong to the mapping's source and target locations.

`connections.py` enables foreign keys, WAL, and bounded busy timeout on writers;
read repositories open SQLite in `mode=ro` and enable `query_only`. Both
repository constructors use the shared cold preflight or the runtime's live
role owner before opening that reader, then check the exact current contract
before exposing it.
Live database paths can be validated against
managed roots before creation; that containment resolver converts long managed
roots only at the native I/O boundary and compares ordinary logical spellings.
This is not a claim that SQLite database files themselves may use overlong
paths. `timestamps.py` is the single fixed-width aware-UTC
representation used by both schemas.

The M1 desktop shell service composes these per-file checks into one
read-only `validate_database_contracts()` preflight returning a
`fresh`/`ready`/`migration-required`/`incomplete`/`refused` pair state — including the
orphaned-sidecar refusals — enforced by the CLI mutation paths and ready for
the Slice 1 product host to consume before window creation, so history cannot
be initialized without the ledger. Cold validation uses the shared immutable or
private-WAL path above, never source SHM recovery authority. Already-owned roles
use current SQLite snapshot validation as described above.
Fresh creation is a separate, serialized workflow operation: it
publishes ledger then history after reserving every main and sidecar cleanup
target through a Windows ownership lease. Failure cleanup derives a new delete
handle from the retained reservation with `ReOpenFile` and requests
exact-object disposition; a displaced foreign pathname is retained rather than
removed through a check/use race. These leases require a stable file identity;
an absent native identity is an `OSError` refusal, never a usable lease token.
Rollback covers ordinary exceptions,
`KeyboardInterrupt`, and `SystemExit`; handles release stepwise and an
incomplete cleanup carries the coordinated reset direction, naming both main
paths. A claim refusal (another process holds a claim on either path) is
raised as itself once cleanup completed, so admission reports it as below
([Maintenance Claim](#maintenance-claim)). It never invokes
the destructive development reset. A crash-shaped one-main pair is
`incomplete`, and the next start creates the missing database. An orphan
sidecar or a `-journal` is refused as `inconsistent-pair` with direction to
preserve the files for inspection, and a database of another role as
`<role>-wrong-role`; neither gets reset advice. Only an empty or unversioned
file, or unsupported metadata, topology or version, is refused with the
manual-reset direction ([Migration](#migration)). None of these mutates.

`repositories.py` returns immutable inventory, run, and `MappingSnapshot`
values. Canonical path, file-identity, and canonical positive-decimal row-ID
selections are queried in chunks bounded by
`connections.QUERY_SUBJECT_BATCH_SIZE` (400) inside one read transaction, so a
concurrent commit cannot split one selection across different database
snapshots. Row-ID lookups are location-scoped, deduplicate in
first-requested order, and omit malformed or missing identifiers rather than
broadening the query. Every supplied path, row-id, and mapping-identity
occurrence also consumes its independent 150,000-entry request wall before
normalization, deduplication, sorting, or query construction. Thus duplicates,
malformed ids, and absent keys within the wall preserve their established
result semantics, while the first raw excess refuses without consuming another
value or starting SQL work.

Query subjects count against the shared batch bound before execution. Path,
integrity, and mapping-pair statements use at most the batch size plus two
parameters, row-ID statements use at most the batch size plus one, and
two-column identity statements use at most twice the batch size plus one.

History (version 9) creates a provisional `history_runs` row at the first durable
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

The current schemas carry the metadata rows in
[Persistence Versions](#persistence-versions). `classify_database` reads only
the catalog and those rows: opening ledger v1-v3, history v1-v7, a v4/v8
database with another contract id, or a current database with a
missing/mismatched row raises `SchemaResetRequired` without altering it; a
released v0.1.0 database raises `DatabaseMigrationRequired` and a newer one
`DatabaseNewerVersion` from every reader and writer admission path.
`reset_databases()` is an explicit
development/test helper that validates both exact paths before deleting their
database/WAL/SHM/journal artifacts and recreates both current schemas; normal startup
never calls it. The reset is intentionally destructive and non-transactional:
all NamiSync and SQLite handles must already be closed, and a locked sidecar can
make a later delete fail after an earlier artifact was removed. The caller must
clear the lock and rerun the coordinated reset/recreation; this helper is not a
user-data recovery guarantee. Forward migration of a released pair is the only
maintenance writer ([Migration](#migration)); backup commands, retention and
export/import are not claimed yet.

`settings.py` owns `SemanticSettingsStore`. A commit takes a deterministic
Windows named mutex, rereads the latest document while holding it, applies only
the supplied patch fields, flushes the replacement payload, and atomically
replaces the UTF-8 JSON file. This prevents two processes editing unrelated
settings from reverting one another. The settings store does not claim
parent-directory write-through across sudden power loss; preferences are not
part of the audit ledger's durability contract.
Schema v2 adds the desktop Setup automatic-verification default. Other schemas
are refused without rewriting or deleting their files. Partial preservation
patches merge creation-time and ACL switches into the latest stored policy under
the same mutex, preserving ADS and omitted sibling switches. A full preservation
replacement cannot be combined with partial preservation switches.
During pre-release development, an old-schema refusal is resolved with the app
closed: move only that data root's `settings.json` aside as a backup and reopen
with fresh defaults. The packaged release uses the root selected by `AppPaths`
(`%LOCALAPPDATA%\NamiSync`); every other run defaults to
`%LOCALAPPDATA%\NamiSync-Development` with the same layout, and an explicit
data-dir selects another root.
Never delete the ledger/history pair or `ui-state.json` for a settings reset.
Reads require the exact integer schema discriminator and reject duplicate JSON
object keys rather than accepting boolean/integer equivalence or last-key-wins
ambiguity.
Before UTF-8 decoding or JSON construction, a binary read stops at one byte
past an exact schema-derived ceiling. The ceiling is the longest fixed
canonical schema document plus six output bytes for each of the filters'
16,384 admitted UTF-8 bytes and the exact quotes/comma expansion for 64 list
items. The canonical writer attains that bound with control-character filters;
arbitrary whitespace or noncanonical JSON that exceeds it is refused even if
its decoded values would otherwise fit. Filter count is checked before the
decoded list is copied into the immutable settings contract, and exact patches
are reconstructed before taking the write mutex so forged frozen fields cannot
bypass validation.
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
- generic namespaced annotations with entity kind/id/key/value and uniqueness;
- restore lineage: backup cuts of ancestor ledger instances and lone-History
  boundaries ([Ledger instance and ids](#ledger-instance-and-ids)).

Since ledger v4, file-index columns and repository
binds use canonical `FileIndex128` text rather than SQLite numeric affinity.
The exact identity domain and native-source rule remain owned by `BRIDGE.md`
and `DEFENSE.md` §1.3.

Successful byte-producing operation transactions return the persisted target
inventory row identity, target location, run scope token, and canonical path
key as one tuple. Idempotent replay returns the identical tuple. Compound
execute→verify reuses one run token/window and the same run-bound recorder for
conditional integrity writes; pause closes/reopens the connection without
ending the row, and terminal settlement fills `ended_at` once.

Official writers keep observed and attested file-identity fields paired and
clear attested-only fields when no content evidence exists. The ledger encodes
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

Every writable ledger connection from the connection factories enables foreign
keys, WAL, bounded busy timeout, and explicit transactions. The migrator's
exclusive connection is the exception: foreign keys stay off so old tables
can be renamed and dropped, and `foreign_key_check` proves the result before
COMMIT ([Migration](#migration)). The serialized writer spends one monotonic
contention budget across its local lock, SQLite busy waits, and retry sleeps;
the transaction body is not misclassified as contention time. Only SQLite
primary result codes `SQLITE_BUSY` and `SQLITE_LOCKED`, including their extended
forms after primary-code masking, are retryable; exception message text never
controls contention handling. Read repositories use read-only connections where
possible. A function named/read-scoped as read-only may never be used for
retention or other writes—the PoC made that error and disabled pruning entirely.

First-time schema creation holds its database's exclusive
[maintenance claim](#maintenance-claim), so a concurrent creator or writer is
refused at once rather than waited for; there is still no pair-scoped startup
mutex or retry loop. A persistent multi-process service must add a pair-scoped
initialization gate and two-process regression before claiming stronger startup
liveness.

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
existing nullable target-identity evidence. This scan-scoped reader does not
derive identity disqualifiers from inventory: retained paths and link counts
describe earlier observations, not simultaneous current aliases. The planner
checks current source/target link counts and identity multiplicity from the
scans, and still requires unique eligible correspondence. Mapping lookup and
all `QUERY_SUBJECT_BATCH_SIZE` target-key batches share one SQLite snapshot;
the bounded result is restored to canonical
source-key/target-key order before
planning. Irrelevant historical location rows are therefore never materialized
by planning. No separate historical snapshot reader is exposed; retained
inventory aliases do not disqualify current scan identities.

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

Execution recorder acceptance uses the core planning metadata/link-count
predicate for NOOP's live observations and TRASH's prior target. Pure
MOVE/RECASE results use the core same-file-version comparison against the
reviewed target: kind, size, mtime and available identity, without attributes,
creation time or link count. Existing exact NOOP/TRASH identity equality remains.
Supplied observations are persisted in full. COPY/UPDATE/MOVE_UPDATE and pure
rename source rows retain the reviewed source snapshot; correspondence consumes
its identity, while future move eligibility uses current scans.

These acceptance rules do not relax optimistic inventory-row concurrency,
integrity subjects, attestation consistency, operation replay hashes or token
conflicts. DELETE still records its exact reviewed prior payload.

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

Unsupported observations preserve known entry kind and nullable raw attributes
and logical file size in the existing observation columns. Repository snapshots
expose those advisory facts separately; unsupported rows still have no usable
`FileStat` and retain unsupported presence; advisory facts do not make them
eligible for verification. A later
unavailable observation clears the previous advisory facts rather than borrowing
them. Missing rows retain their last evidence as historical evidence, not current
residency. Existing databases need no schema or epoch change; old unsupported
rows without these facts remain unknown. Inventory receipt hashes include new
facts when supplied and retain the old projection when both fields are absent.

Remembered-location readback derives source, target and pair suggestions from
durable sync run activity joined to its active mapping. It excludes soft-deleted
mappings, deduplicates stable location or pair identities, orders by newest run
time with an identity tie-break, and applies a five-result SQL limit to each
collection before materializing values. The three collections share a read
snapshot. Run outcome does not erase history: failed, canceled, degraded and
unfinished runs remain eligible, as do offline or remounted locations.
No write occurs merely from reading, typing, picking or probing. Stored mount
hints remain non-authoritative labels; workflow activation resolves identity
again. This adds neither a schema/index migration nor query-time certification.

Missing marking uses temp tables or bounded batches, not a giant `NOT IN` list.
It runs only after a complete online scan of the declared scope. `FULL` uses an
all-location observed-key anti-join, exact `PATHS` updates only absent named
keys, and `SUBTREES` bounds the same anti-join to exact paths plus each root
equality and descendant range. The existing
`inventory_location_presence_idx(location_id, presence, rel_path_key)` supports
the default-binary literal range `root || '\'` through `root || ']'`; no
`LIKE`, collation change, schema migration, or ledger version bump is involved.
Missing rows retain evidence and may be acknowledged/restored/reappeared.
Tombstone pruning is unrealized and requires an explicit policy with impact
review; it is not incidental scan cleanup.

Stale-inventory reads include rows with no evidence, no true verification time,
an age-expired verification, a durable invalidation, or a current/attested stat
contradiction. A matching later scan cannot erase a prior mismatch or drift;
only a guarded positive evidence transaction can make the row current again.

## Schema Evolution

Status: implemented by M2-A3 (2026-11-25): classification in `schema.py`, the
migrator in `namisync/db/migration.py`, pair admission in
`namisync/workflows/database_pair.py`. Tests: `tests/test_db_migration.py`,
`tests/test_database_pair_migration.py`, `tests/test_cli_migration.py` and the
desktop startup cases in `tests/interfaces/web/test_host.py`.
v0.1.0 “Gertrud” released ledger v4 and history v8. From M2 on, a released
database migrates forward or is refused: never reset, never half-migrated and
never migrated under a writer. [M2_PLAN](M2_PLAN.md) holds the checkpoint's
outcomes, gate and non-goals.

[DEFENSE §2.5.4](DEFENSE.md#254-migrating-a-released-database) sets two
postures. A step from an M2 or later database meets its requirements in full.
The import from v0.1.0 runs on the same engine as best effort, and what it
adds is confined to three places: the steps registered in `MIGRATION_STEPS`
for ledger v4 and history v8, the released-topology classification in
`schema.py`, and the fixture under `tests/assets/v0_1_0/`. A new step for a
later version adds a registered step, a format row or schema version, and a
saved fixture of the version it migrates from; it reads and writes only its
own database, and the pair operation supplies anything that needs both.

### Formats and metadata

- Core owns one version constant for each shared format a database persists,
  in `namisync/core/formats.py`: the event envelope, content evidence, the
  recording contract, the canonical hash preimage, file identity text, numeric
  text and canonical path keys. Each constant has known-answer vectors in
  tests, held as literal bytes or digests per version. An encoding that changes
  without a new constant fails its vector; a new constant without a vector
  fails too.
- `schema_metadata` holds separate rows instead of one contract string: `role`,
  `schema_version` and one `format.<name>` row per embedded format. The ledger
  also holds `instance_id`. The `contract_id` and `data_epoch` rows are gone.
- Schema code declares which formats each database embeds: every format whose
  vectors pin an encoder or vocabulary that produced stored text, a hash or a
  token. The ledger embeds all seven: event vocabularies
  (`recording_commands.disposition` as `RecordDisposition`, decoded on replay;
  `runs.filesystem_status` as `SessionState`, also hashed into
  `finish_payload_hash`; `operations.outcome` as `Outcome`; `operations.kind`
  as `OperationKind`; `IntegrityMode` in integrity payload hashes), evidence
  columns and digests, `FileIndex128` text, integers decoded under the numeric
  bounds, path keys, plan fingerprints, selection digests, operation tokens
  and payload hashes over core projections (preimage), and recording status
  text and command vocabulary. History embeds event (envelopes and receipts),
  numeric (decimal scalar text inside them and the safe-integer column
  checks), preimage (operation item ids, which are deterministic operation
  ids, and the item identity hashes over them) and recording facts. A test pins the formats of every schema
  version, so a core format cannot change under a database without a new
  schema version, and every version from the oldest supported source to the
  current one has a registered step (`MIGRATION_STEPS`).
- At open, a database is current, older and supported, newer, at the wrong
  path, or refused. A newer database (a `role` row naming the expected role,
  and a schema version or a `format.<name>` row above this NamiSync's) is
  refused with direction to use the NamiSync that wrote it, never with reset
  guidance. A database that is recognisably the other role (a `role` row
  naming it, or no `role` row and the other role's released contract id) is
  refused as `DatabaseRoleMismatch`: the two paths look swapped, check them;
  no reset and no "newer" text. A `role` row this version does not know (only
  a newer NamiSync could write one) is also `DatabaseRoleMismatch`: the file
  is not a database of the expected role this version knows, check the path;
  no reset and no "newer" claim. Any other role-less database above the current
  version is refused as unsupported. The only supported source is v0.1.0's format:
  ledger v4 or history v8 with its released contract id, no `role` row, and
  exactly the released topology. `data_epoch` is not read; every such database
  is treated as epoch 8 (user decision, 2026-11-19).
- Each database is judged and migrated on its own, in its own transaction (user
  decision, 2026-11-17). A pair left at different versions by an interrupted
  upgrade therefore finishes on the next start, and pairwise agreement follows
  from each role matching the application's current formats.

### Ledger instance and ids

- The ledger gets a random `instance_id` when it is created, or when a v0.1.0
  ledger migrates. Every history run records the ledger instance it was
  recorded against. Runs already in a v0.1.0 history are stamped with a
  ledger's instance only when the same pair upgrade, under the same held
  claims, migrated that ledger from 0.1.0 in that call (user decision,
  2026-11-26, replacing the lineage marker of 2026-11-25). The decision is one
  in-memory fact of the call; the ledger records nothing for it. In every
  other case the History migrates unstamped and its runs are `earlier`: the
  ledger was already current when the call began (a fresh one, a restored
  one, one created because it was missing, or one whose migration an
  interruption separated from History's), or there is no ledger at all
  ([One database missing](#one-database-missing)). The stamp is a column of its own (`history_runs.ledger_instance_id`,
  32 lowercase hexadecimal digits), outside the run's context hash, so no
  stored hash is reinterpreted. A trigger makes it write-once, since no hash
  covers it, and a history observer refuses to reopen a run under a different
  stamp ([HISTORY](HISTORY.md)). The column is nullable: the runtime, the only production writer,
  always supplies it from the ledger it admitted, but direct `HistoryStore`
  writers in tests and measurement tools have no ledger. The read rule below
  places a run with no stamp in an earlier ledger.
- **Restore lineage** (M2-A4, user decisions 2026-11-20 and 2026-11-25). Ledger
  v5 holds `ledger_lineage`, added to the unreleased schema in place with no
  new version or migration step. A `backup-cut` row `(X, T)` says that History
  runs recorded against ledger instance X that started before T belong to this
  ledger. A backup carries a cut naming the instance it was cut from, and a
  restore keeps the backup's lineage under a new instance id, so the
  predecessor is the ledger the backup was cut from, not the one the restore
  replaced. A `replaced-missing` row (no instance) is the boundary written when
  a lone History gains a new ledger; it joins nothing. `at` is canonical UTC
  text, an instance appears at most once, and CHECK constraints tie the
  instance to the kind. The kind list was amended in place on 2026-11-25 to
  add `migrated-released` and amended back on 2026-11-26: a schema-5 ledger a
  source-tree run created or migrated while that kind was allowed, with or
  without such a row, fails the exact topology check and is refused with the
  reset direction. Fresh creation and migration both create the table empty.
  A backup writes its own cut into the copy only, and restore keeps the
  backup's rows ([Data Protection](#data-protection)). A ledger created
  because it was missing beside a History has exactly one `replaced-missing`
  row, written in its creation transaction with the creation time
  ([One database missing](#one-database-missing)). No reader uses that row
  yet: the read rule below already places every run of the kept History in an
  earlier ledger, and the History page that shows the boundary comes later.
- **Read rule.** A History run is `current` when its stamp is the ledger's
  instance, or when a `backup-cut` names its stamp and the run started strictly
  before that cut; a run that never started is judged by its creation time.
  Every other run, one with no stamp included, is `earlier`. When no usable
  ledger was read (missing, damaged, refused or not named), every run is
  `unknown`, and History is still listed. `LedgerRepository.ledger_lineage`
  reads the instance and its cuts in one snapshot; the runtime reads it once
  after the History read, so these are two snapshots, and a restore between
  them only leaves the view behind. Times are compared as recorded wall-clock
  UTC, so a clock set back across a cut can misplace runs near it; this is
  disclosed, not defended. Cross-database lookups, which resolve a run's
  location, mapping or inventory ids in the ledger, apply only to `current`
  runs. No reader performs one yet; later readers must keep to this.
- **A backup copied into place by hand is refused.** A live ledger whose
  lineage has a `backup-cut` naming its own `instance_id` can only be a backup
  file copied over the ledger, since restore always issues a new instance id.
  Admission refuses it with `LedgerIsBackup` (pair reason `ledger-is-backup`)
  everywhere a ledger is admitted: the cold probe, live owners, repositories,
  recorders, the CLI pair refusal and desktop startup. The direction is to put
  back the ledger it replaced or restore the backup with
  `namisync restore ledger <backup file>`, never to reset, and nothing is
  changed ([Data Protection](#data-protection) and
  [COMMANDLINE](COMMANDLINE.md#maintenance-commands)). The rule runs last in the ledger reader
  contract, once role, version, formats, instance id and exact topology have
  passed, and `classify_database` never applies it. Backup verification can
  therefore classify its copy as a current ledger and accept exactly this
  refusal; check and restore-source validation read the fact itself
  (`ledger_backup_cut`) after their one classification. A ledger carrying only other instances' cuts is
  admitted normally; standalone `history` treats a refused ledger as unusable
  and marks membership unknown.
- A schema-5 ledger made by a source-tree run before the table existed fails
  the exact topology check and is refused with the reset direction, like any
  other unsupported topology (user decision, 2026-11-25). Tests for lineage,
  the read rule and these refusals: `tests/test_ledger_lineage.py`, the
  history and backup cases in `tests/test_cli.py`, and the startup case in
  `tests/interfaces/web/test_host.py`.
- An id referenced from outside its own database is never reused (user
  decision, 2026-11-21). A plain `INTEGER PRIMARY KEY` hands a new row the
  highest id plus one, so deleting the highest-numbered location would give its
  id to the next new one, and History would resolve the old runs to the new
  path. M1 never deletes such rows; forgetting, purging and pruning will. The
  design-time inventory (2026-11-25) found:
  - `locations.id` and `inventory.id` are stored durably outside the ledger:
    History keeps a location id as a run's `subject_id` and both ids inside
    integrity event envelopes.
  - `locations.id`, `mappings.id` and `inventory.id` are held for a process
    lifetime by task setup, recent pairs, inventory review and the
    `--location-id` argument.
  - Nothing outside History refers to a History row id; runs are named by
    token.

  `locations`, `mappings` and `inventory` therefore use `AUTOINCREMENT`, and no
  History table needs it. A table whose ids start to leave its database later
  gets it through a migration.
- A sync plan records the ledger instance it was planned against (M2-A4, user
  decisions 2026-11-20 and 2026-11-24). The runtime reads it when it prepares
  planning, before the plan reads the ledger, so a replacement while it plans
  is caught too. A fresh pair gives none, and a plan with none reads no ledger:
  it plans against empty correspondence even when another process creates the
  pair before its correspondence step, so a plan never reads a ledger it does
  not record (`tests/test_workflows.py`). Commitment copies it into the core `Commitment`, which every held,
  queued or paused execution carries in its checkpoint; nothing re-reads it.
  - **At start and every resume**, before observation, preflight, any
    filesystem change or ledger write, a different current instance is a
    commitment refusal: a fresh start ends `REFUSED+UNRUN` with “The ledger was
    replaced (restored or reset) after this plan was made, so it cannot run.
    Plan again to review it against the current ledger.” The CLI prints it with
    “Rerun the same sync command to review a new plan.” as its last sentence and
    exits 3; the desktop shows the commitment refusal (“Execution commitment is
    invalid. Restart task with Plan Again.”), since no diagnostic text crosses
    the bridge. No ledger row is written; History keeps the attempt as a
    finalized run with filesystem `refused` and disposition `unrun`, stamped
    with the current instance it was admitted under. A resumed execute
    continuation ends `FAILED+RAN`, and a resumed verify continuation keeps its
    execute status with an incomplete verify phase; in both the existing run is
    not finished in the replaced ledger, so ledger recording is degraded.
  - **Under the claim.** Each ledger writer a sync run opens (the run recorder
    at start and on each resumed stretch, cancel settlement, and existing-run
    finishing) checks again after `LedgerRecorder` takes the ledger's shared
    claim and before its first write. Restore needs that claim exclusively, so
    the instance cannot change between this check and the writes. The start
    check itself runs while the session's History observer holds the ledger's
    shared claim, taken before its stamp was read, so this second check fires
    only when a replacement lands after the start check without that claim
    (degraded audit). It fails closed through the recording-open-failure path: no ledger
    write, no filesystem change, `FAILED` with recording degraded and the typed
    `LedgerInstanceChanged`, CLI exit 4.
  - **First use.** A plan with no instance starts against whatever ledger
    exists at execution. The run's first recorder reads the instance under
    its claim, before its first write, and the runtime keeps it beside the
    run's start time for as long as the run can resume. From then on it
    stands in for the planned instance: each resume's start check and every
    later ledger writer of that run compare against it, with the same
    refusals and wording as above.
  - Inventory review's row-id actions (acknowledge, restore) are not plans and
    are not covered here.
  - The CLI case in `tests/test_cli.py` runs a real in-place restore while the
    plan waits at the prompt. The other replaced-ledger cases stand in for
    restore by rewriting the id under the ledger's exclusive claim:
    `tests/test_bridge_resume.py` (start, paused execute and verify resumes of
    a run admitted without an observer, the under-claim check) and `tests/interfaces/web/test_drain.py`.
    The first-use resume refusal in `tests/test_bridge_resume.py` restores a real pre-execution backup
    while the run is paused.
- A paused integrity session (baseline, verify, rebaseline) records the ledger
  instance its saved progress belongs to (user decision, 2026-11-26). Each
  stretch reads the instance right after its `LedgerRecorder` takes the
  ledger's shared claim, and the continuation keeps it beside the saved
  selection and completed items; a run with no saved progress yet keeps none
  and compares nothing. On resume a different instance is refused
  at that same point, before the inventory scan, any ledger write or reuse of
  the saved progress, through the recording-open-failure path: `FAILED+RAN`,
  recording degraded, typed `IntegrityLedgerChanged` (“The ledger was replaced
  (restored or reset) while this baseline run was paused, so it cannot resume:
  the results it reported before the pause belong to the replaced ledger, not
  the current one. Start a new baseline run against the current ledger.”).
  Restore always issues a new instance, so a restore from a backup taken
  moments earlier is refused too. The workflow holds no claim across the
  pause, so restore stays available unless a healthy History observer holds
  its claims. Items reported before the pause stay in the
  session's terminal record, exactly once: they are the run's account of
  what it did, and the message says they belong to the replaced ledger. A
  view that presents one as the current ledger's attestation is defective. Inventory does not pause. Tests:
  the restored-ledger, audit-failed, placement and under-claim cases in
  `tests/test_inventory_runtime.py`, with a real in-place restore.

### Migration

Migration runs in the CLI before a mutating command's admission and at desktop
startup, before the first ordinary connection. It is automatic and says so.
Read-only classification never migrates and never writes a database artifact
or a `.claim` file: `validate_database_pair` reports `migration-required` (reason
`ledger-older`, `history-older` or `pair-older`), and a command that only
reads, such as standalone `history`, refuses an older database with direction
to start NamiSync once.

When one role needs a reset, pair classification still classifies the other
before it answers. A newer database or a wrong role there (or a ledger
backup in place, damage, or a read failure) is reported in preference to the
reset, because such a database cannot be judged usable. Each role that needed
the reset is then read once more, and the reset is returned only if it still
needs it; otherwise the whole classification repeats (bounded, ending in
`database-busy`). Both needing it gets reason `ledger-contract` and the
direction to discard both, naming each main by its path. One
needing it beside a peer validated as current or older gets reason
`<role>-contract` with a direction (`reset_direction` and `guidance`) naming
only that database's path and sidecars, to keep the peer's path as it is, and
what follows: the pair is then [incomplete](#one-database-missing), so the
next start or sync or inventory command creates a new one (a new ledger
leaves the History's runs belonging to an earlier ledger; an older peer is
updated first), or `namisync restore <role> <backup file>` replaces it.

The CLI migrates only after the command's own roots and `--path` values are
admitted with every database outside the roots (`database_placement_admitted`, which opens no
database). When a root or path is refused, or a root holds a database, nothing is migrated and
the command's ordinary admission reports the input error. Workflow admission
never migrates: a pair that is still `migration-required` there is refused
with the migration direction, so a pre-check that failed transiently
ends in a refusal and the next run migrates with its notice. A command given `--location-id` has
no root to check until the ledger is read, so there the pair migrates first
and the placement check follows.

`upgrade_database_pair` is the one operation that migrates or completes a
pair; the CLI and the desktop call it once (through the runtime's and the
service's `upgrade_database_contracts`) and report what it returns: the final
contract, the databases it migrated and those it created. Its caller states
whether it may create a missing database (`create`). It classifies the pair
cold and returns, unchanged and with no claim taken, any state other than
`migration-required` or `incomplete`, and `incomplete` too without that
permission. Otherwise it takes both exclusive claims and classifies again
under them; an incomplete pair is completed as in
[One database missing](#one-database-missing). For an older
pair it runs the delete-access probe (step 1) on both main files before
either migrates, so a process holding only History refuses the pair with both
databases unchanged. Then `migrate_database` runs for the ledger, then for
History: with the ledger's instance id when this call migrated the ledger
from 0.1.0 ([Ledger instance and ids](#ledger-instance-and-ids)), otherwise
unstamped. Each call migrates an older database or, for a current one, only
confirms it, so a pair an interruption left half done finishes on the next
call, with History unstamped if the ledger had already migrated. Neither
adapter's migration notice says whether History was stamped: the rule above
decides it, and History readers show each run's membership. Its refusals
return a `refused` contract with
guidance and no reset direction: `database-in-use` (a claim or an open
handle), `backup-failed` (step 2), `migration-failed` (the rollback below,
naming the backup) or `migration-unavailable` (an access or stability
failure). A refusal leaves both databases as they were, apart from a ledger
that had already migrated when History's own step then failed. A swapped
pair, or a database of a role this version does not know, is refused with
reason `ledger-wrong-role` or `history-wrong-role` by the cold classification,
before any claim is taken. `ensure_database_pair` creates a fresh pair but
never migrates or completes; it refuses an older pair with the migration
direction and an incomplete one with the completion direction.

For each database that needs it, ledger first:

1. **Exclusive access.** `migrate_database` takes the database's held
   exclusive claim (`hold_maintenance_claims` yields both as
   `MaintenanceClaims`) and refuses any other. It then proves through the
   files that nobody else is using the database, whatever their version.
   First, opening the main file with delete access (sharing read, write and
   delete) must succeed, which fails while any other handle is open without
   delete sharing: every SQLite connection, opened or idle, and the handle a
   desktop pins (`WindowsPathLeaseNative`). The probe handle closes again,
   because SQLite's own handle does not share delete. Then one connection
   (busy timeout zero) sets `locking_mode=EXCLUSIVE` and runs
   `BEGIN EXCLUSIVE; COMMIT` before any other access, and keeps the lock until
   migration ends. SQLite refuses that lock while another connection holds a
   read or write lock, and while it is held no other process can read or
   write. Either refusal is `DatabaseInUse` with no change to any file.
2. **Backup.** From the exclusive connection the SQLite backup API copies the
   committed database, WAL content included, to `<main>.migration-<random>.tmp`
   beside it. That file is created exclusively, so a file already at the name
   refuses the backup and is neither reused nor removed. The copy is switched to rollback-journal mode so it stands alone,
   checked (`integrity_check`, classification as the source version, and every
   table's row count against the source), flushed with `fsync`, and renamed to
   `<main>.backup-v<source version>-<UTC yyyymmddThhmmss + microseconds>Z`.
   A Windows rename never replaces an existing file, so a name collision
   refuses. No backup, no migration: any failure is `DatabaseBackupFailed`
   (pair reason `backup-failed`) and nothing is changed. Its guidance depends
   on the cause. A backup that fails verification (its `integrity_check`, its
   classification or its row counts), or a copy that SQLite reports as corrupt
   or not a database, means the source itself is damaged, because the backup
   is a page-for-page copy: the message says the database failed SQLite's
   integrity check and to keep the files and sidecars for inspection, with no
   free-space, reset, archive or delete advice. A failure to write, flush or
   publish says to check write access and free space (updating needs roughly
   three times the database's size beside it). A temporary left by a crash is never read,
   reused or removed, and is not a backup.
3. **One transaction.** Foreign keys are off on this connection (they cannot
   change inside a transaction), so renaming and dropping cascade nothing. Old
   triggers and explicit indexes are dropped and every old table renamed to
   `_migration_old_<name>`; the tables and indexes are created by the shipped
   statements, so a table with no source, such as `ledger_lineage`, starts
   empty; rows are copied with explicit column lists, keeping every id
   (History runs gain the instance id the pair upgrade passes, that of the
   ledger it just migrated, and otherwise, given none, stay unstamped); the
   old tables are dropped; the
   shipped triggers are created; metadata is written. Triggers come after the
   copy: the rows were admitted under identical triggers, and History's append
   guards would refuse events of an already finalized run. Copying explicit
   ids into `AUTOINCREMENT` tables sets `sqlite_sequence` to the highest. The
   result has exactly a fresh database's topology.
4. **Verification before commit.** `integrity_check`, `foreign_key_check`, the
   full current reader contract (role, version, formats, instance id and the
   exact topology), per-table row counts and the ledger's stamp on every
   History run (none on any when unstamped) all
   pass, or the transaction rolls back and `DatabaseMigrationFailed` names the
   backup. A failure raised by COMMIT itself does not claim the database is
   unchanged, since the commit may already be durable: the message says the
   update could not be confirmed and that NamiSync checks the databases again
   at the next start.
5. **Close.** After COMMIT, closing checkpoints the WAL into the main file and
   removes it. v0.1.0's stale `-shm` stays; the exclusive connection never used
   it, and the next ordinary opener reinitializes it. The cold probe ignores
   source SHM, so the next probe and the next ordinary open both succeed. A
   refusal or rollback closes without that checkpoint, so the files stay as
   found apart from an uncommitted WAL tail.

A failure or interruption at any point leaves the old database or, after
COMMIT, the new one: the transaction is all or nothing, and an uncommitted WAL
tail is discarded at the next open. Migration is then refused with the reason,
and the backup stays. There is no automatic restore, because nothing partial
is ever published. Maintenance restore takes only current-schema backups and
refuses a migration backup, which is put back by hand to return to 0.1.0.
Rotation never removes migration backups ([Data Protection](#data-protection)),
so each migration leaves one backup per database and each interrupted attempt
may leave another.

Cost: each database is copied in one transaction, so time and WAL growth are
linear in its size, the WAL holds roughly a second copy until the closing
checkpoint, and the backup needs a third database-sized file beside it. No
size limit is enforced or measured; this is a diagnostic statement under
[DEFENSE §7](DEFENSE.md#7-quantitative-evidence-and-measurement-authority).

The desktop announces a migration only in its log, as
`startup.databases_migrated ledger=v4 history=v8` with roles and source
versions and no paths, since an ordinary startup logs no filenames or paths. The
backups sit beside the databases under the name in step 2. An in-window
notice would need a bridge addition and is not built. The CLI prints one line
naming the databases that migrated and their backups.

#### Migration limits

Limits of the v0.1.0 import, left as they are under
[DEFENSE §2.5.4](DEFENSE.md#254-migrating-a-released-database) (its questions
3 and 4):

- A command given `--location-id` migrates before placement is checked. It
  matters only for a v0.1.0 database moved inside one of its own registered
  roots.
- A v0.1.0 main file copied without its `-wal` migrates as the empty database
  it is, because v0.1.0 keeps its committed rows in the `-wal`.
- The backup temporary's `-journal` sibling is not reserved.
- A process that opens a database between the delete-access probe and the
  exclusive lock without reading is not refused; its first read is refused
  while migration holds the lock.
- The backup rename's directory entry is not forced to disk beyond the file
  `fsync`. Optional `sqlite_stat*` tables are left in place and may hold
  stale statistics for the rebuilt tables, which affects only query planning.
- A v0.1.0 process holding no handle when migration runs is not seen. It
  cannot write afterwards, because its exact-contract check refuses the
  migrated database, but its message still suggests archiving or deleting the
  pair. A released binary cannot be changed, so the release notes carry the
  warning (M2-R1).
- Migration backups are never rotated: they are the only way back to 0.1.0
  and restore refuses them. Each attempt that fails after publishing its
  backup therefore leaves another full backup until the user removes it, and a
  rolled-back attempt leaves the WAL grown with a discarded tail (148 MB to
  296 MB at 400,000 ledger rows).
- The stamp decision is a fact of one upgrade call. An interruption after the
  ledger's migration commits and before History's leaves the next call to
  migrate History unstamped, so a genuine pair's 0.1.0 runs show as belonging
  to an earlier ledger; nothing is lost (user decision, 2026-11-26).
- v0.1.0 records no shared pair identity, so the decision trusts the paths:
  an unrelated v0.1.0 History that sits beside the v0.1.0 ledger when one
  call migrates both is stamped with that ledger's instance, and its runs show
  as current for a ledger they were not recorded with, every file kept.

Left as it is after M2-A4:

- A damaged v0.1.0 database is refused at every start with direction to keep
  its files. Restore replaces a database that fails admission, but only from
  a current-schema backup, which a database still at v0.1.0 cannot have. The
  migration's own damaged-source message therefore stops at keeping the files
  and does not point to `namisync restore`. A damaged database met by
  cold admission before its version can be read gets the shared damage text,
  which points to `namisync check` and to `namisync restore` only conditionally
  (with a backup made by `namisync backup`; [Data Protection](#data-protection)).

Legacy import or merge is separate from migration. It never guesses
volume/location correspondence.

### One database missing

Status: implemented by M2-A4 outcome 5 (2026-11-25), since 2026-11-26 as
the incomplete branch of `upgrade_database_pair`
(`namisync/workflows/database_pair.py`) over
`create_database` (`namisync/db/maintenance.py`). Policy (user decisions,
2026-11-20): with only a ledger, create a History and tell the user; with only
a History, tell the user, create a ledger with a new instance id and record a
durable lineage boundary. The old History is kept and never treated as
describing the new ledger, and ledger records are never rebuilt from History.
Tests: `tests/test_database_pair_completion.py` (real child processes: kills
per stage, claims and open handles), `tests/test_cli_completion.py`, the
startup case in `tests/interfaces/web/test_host.py` and the backup and restore
cases in `tests/test_database_maintenance.py`.

- **Classification.** With exactly one main present, no `-wal`, `-shm` or
  `-journal` of the missing one and no journal anywhere, the present database
  is classified on its own. Its refusals are returned unchanged (damaged,
  newer, wrong role, a ledger backup in place), except that a reset names
  only the present database file and its sidecars and says where the other
  was looked for, so a mistyped path is noticed. Current or
  older and supported, the pair is `incomplete` with reason `ledger-missing`
  or `history-missing` and guidance naming the missing database, how to
  create it (start NamiSync, or run a sync or inventory command, once) and
  that the other is kept; an older present database adds that it is updated
  first with a backup beside it. Orphan sidecars and journals stay
  `inconsistent-pair`. Classification still writes nothing.
- **Admission never completes.** `ensure_database_pair` and planning refuse
  `incomplete` with that guidance, as they refuse `migration-required`. Only
  `upgrade_database_pair` creates the missing database, and only when its
  caller permits it; its callers report it. It holds both exclusive claims,
  ledger first, and classifies again; under them an older pair is migrated as
  in [Migration](#migration) and any state but those two is returned
  unchanged. Without permission, `incomplete` is returned as found whether it
  was seen cold or only under the claims: the present database is not
  migrated and no folder or database is created. The missing
  database's folder is created before the claims, because its claim file
  lives there; when nothing is created, the folders the call made are removed
  again if still empty (one holding the claim file of a refused attempt
  stays).
- **The present database.** A v0.1.0 one migrates first, as in
  [Migration](#migration), open handles refused. A lone v0.1.0 ledger
  migrates as in a pair. A lone v0.1.0 History migrates with no instance id:
  its runs keep no stamp, because stamping them with the
  new ledger's id would make them current and resolve their ids against a
  ledger they were never recorded with. Migration comes before creation, so
  an interruption leaves a lone current database; and a later upgrade never
  stamps a 0.1.0 History beside the ledger created here either, because that
  call does not migrate the ledger. A current present database is not opened for writing
  and keeps its bytes; its runs keep whatever instance they recorded.
- **Creation.** `create_database` builds `<main>.create-<random>.tmp`,
  created exclusively, from the shipped statements and metadata in one
  transaction; a ledger gets `new_instance_id()` and its one
  `replaced-missing` row (instance NULL, `at` the canonical UTC time read
  once both claims are held) in that transaction. The image is verified
  (`integrity_check`, `foreign_key_check`, the full current reader contract,
  the id and the single lineage row), switched to the WAL header with no
  sidecars left, flushed and renamed into place; the rename never replaces a
  file, so a file that took the name refuses with `creation-failed` and
  nothing published. Schema creation and pair initialization are not reused:
  schema creation takes its own exclusive claim, which conflicts with the
  held pair claims, and reservation-based creation can leave an empty main
  after a kill, which reads as a reset beside the good database. The pair is
  then classified again and is `ready`.
- **Refusals** return a `refused` contract with no reset direction:
  `database-in-use` (a claim on either path, or a handle on a present v0.1.0
  database), `backup-failed` and `migration-failed` as in migration,
  `creation-failed` (write access or free space), `completion-unavailable`.
  A History migrated before a creation that then failed stays migrated and
  unstamped, and the next call creates the ledger.
- **What a kill leaves** (tested at each stage). Before the rename: the
  missing database still missing, an image temporary (with its own
  `-journal` mid-transaction) never reused or removed, and a lone v0.1.0
  database either as it was or migrated; the pair is `incomplete` and a rerun
  finishes. After the rename: `ready`. No stage leaves an empty or partial
  main or reset guidance.
- **Telling the user.** The CLI completes where it would migrate, after the
  same placement admission ([Migration](#migration)), except that a command
  given `--location-id` refuses instead (exit 3, nothing created), because no
  root is given to check the new database's path against. Such a command
  never permits creation, so it refuses the same way when a database is found
  missing only under the upgrade's claims. It prints one line per
  created database, after the migration line when the present one migrated
  ([COMMANDLINE](COMMANDLINE.md)). The desktop completes before binding and
  logs `startup.database_created role=<role> reason=missing` with no path,
  beside `startup.databases_migrated`; an in-window notice would need a bridge
  addition and is not built. The read-only `history` command never completes
  a pair.
- **Maintenance.** `check` reports each role in any pair state; `backup`
  needs a ready pair and returns `incomplete` with its guidance otherwise;
  restoring a ledger beside no History or a History beside no ledger leaves
  the pair `incomplete`, and the next start completes it.
- **Limits**, disclosed under [DEFENSE §2.5](DEFENSE.md#25-proportional-defense):
  the rename's directory entry is not forced to disk beyond the image's
  `fsync`, as for migration backups.

## Maintenance Claim

Status: implemented by M2-A3 outcome 1 (2026-11-25) in
`namisync/db/claims.py`. Its maintenance consumers are migration
(`namisync/db/migration.py`) and, since M2-A4 outcome 4, check, backup and
restore (`namisync/db/maintenance.py`, [Data Protection](#data-protection)).
User decisions (2026-11-20, 2026-11-24).

Maintenance (migration, check, backup and restore; later archive-and-reset,
reclaiming file space, history pruning and purge) must not run while any run's
records are still being written to either database, in any process.

- **Owner.** The db layer, because only its writers know when a run's last
  write has landed. The dispatcher stays domain-blind.
- **Mechanism.** Each database has a lock file beside its main file, named
  `<main>.claim`. A claim is a `LockFileEx` lock on byte 0, length 1, shared or
  exclusive, always with `LOCKFILE_FAIL_IMMEDIATELY`: it never waits. Release
  unlocks and closes the handle; Windows also drops the lock when the handle
  closes or the process dies, including while a child of the holder lives.
  Locks belong to handles, so two claims in one process conflict exactly as two
  processes do. The file is opened with Python's own `os.open` (extended-length
  spelling; non-inheritable, as every Python-opened handle is) so the test
  suite's live-data guard sees its creation. `claim_path` resolves the main path
  with `validate_database_path`, the resolution every database caller already
  applies, so spellings that resolve alike share one claim. The file is created
  on demand by schema creation and writers, and never deleted. It is not a
  database artifact: fresh-pair detection, `database_artifacts_present` and pair
  reservations consider only the main file and its `-wal`, `-shm` and `-journal`
  sidecars, and the desktop path lease (`AppPathLease.bind_databases`) pins only
  the two main files. Neither database path may be the other's, or the other's
  with `.claim`, `-wal`, `-shm` or `-journal` added (compared ignoring case, as
  Windows does): taking the claim would create the other's main, and SQLite
  would overwrite it as a sidecar. `require_distinct_database_paths` refuses
  such a pair with `ValueError` naming the overlap before any file is opened:
  in the service constructor, which every adapter reaches first (the CLI's
  `Configuration error`, exit `2`), in `validate_database_pair`, and before
  check, backup and restore take their claims.
- **Refusals.** `DatabaseClaimRefused` extends `DatabaseAdmissionError`, as
  `DatabaseBusyError` does, so a claim refusal is an admission refusal to
  existing handlers; each carries the main file's `path`.
  `DatabaseMaintenanceActive` refuses a shared claim under an exclusive one
  (new work is refused, not queued); `DatabaseInUse` refuses an exclusive claim
  under any other. Failure to open the claim file raises the `OSError`
  unchanged, never a claim refusal, and creates nothing. In a directory that
  forbids new files SQLite's own `-wal` and `-shm` creation would fail too; a
  directory at the `.claim` name, or a missing parent, is a failure only the
  claim has. A `LockFileEx` error other than `ERROR_LOCK_VIOLATION` is likewise
  raised as an `OSError`, not reported as contention.
- **Writers hold it shared.** `LedgerRecorder` takes its database's claim after
  any schema creation has released its exclusive claim and before its writer
  connection opens, and releases it after that connection closes; a failed
  close keeps it until a later close or process exit, and every constructor
  failure releases it. A recorder lives for one run or one resumed stretch, so
  a paused run's recorder holds none. Each `HistoryObserver` holds History's claim from
  construction at admission until `close()`, across pauses and after
  `finalize`, because the History connection is shared and outlives runs;
  `close()` releases it after its final flush attempt, even a failed one, and
  construction failures release it. `HistoryStore` holds none. The runtime's
  observer for an admitted run also holds the ledger's shared claim for that
  lifetime: taken before History's and before the stamped ledger instance is
  read, released when the observer closes, after History's, and by every
  failure while opening. A writer refused
  because maintenance holds the claim fails its admission with a typed refusal;
  new runs are refused, not queued.

  **Admission refuses** (M2-A4). Both shared claims are taken when the
  dispatcher's audit-observer factory (`LocalWorkflowRuntime.audit_observer`)
  opens the session's observer: the ledger's first, in maintenance's order,
  then History's, and both before either database is opened for it, so a
  restore that began after preparation refuses the session instead of
  failing the History open as an audit failure (`tests/test_inventory_runtime.py`,
  a child-process History restore stopped mid-copy, naming the run's ledger
  and another). The ledger instance the observer stamps on the History run
  is read once, under the ledger's claim. A `DatabaseMaintenanceActive` on
  either becomes the core `SessionAdmissionRefused`, which the dispatcher
  raises to the submitter before anything is stored, published, attached or
  queued, with any claim already taken released; every other factory failure
  still degrades audit. A session is therefore either refused at admission or
  admitted holding both claims, and while its observer is open every
  maintenance attempt naming its ledger, whichever History it names, is
  refused (`DatabaseInUse`, `database-in-use`), so no restore replaces the
  ledger a run's stamp names while the observer is open
  (`tests/test_inventory_runtime.py`, for execution, inventory and integrity,
  with maintenance naming another History). Sessions without an audit observer
  (planning) write neither database and are not refused. A session whose
  audit is degraded holds neither claim until its ledger recorder opens, and
  that recorder refuses it as below.

  First use is refused the same way. Creating a fresh pair
  (`initialize_database_pair`) holds both exclusive claims from before its
  first file is reserved until the pair is published, and classifies the pair
  again under them, so a pair another process created meanwhile is used as it
  is. A claim that is refused (`DatabaseInUse`, for example while `check`
  holds the absent pair or another process is creating it) refuses before
  anything is reserved; `ensure_database_pair` turns it into
  `SessionAdmissionRefused` with the claim's own retry message (CLI exit `3`).
  A folder or claim file that cannot be made is a
  `DatabasePairInitializationError`, like any failure while creating.
  Desktop startup creates a fresh pair itself and shows that message in its
  startup error.
- **Admission tells a pair in use from an unusable one.** A pair that does
  not classify as fresh or ready is classified again while its shared claims
  are held (`classify_database_pair`, used by `ensure_database_pair`, the
  runtime's `validate_database_contracts` and the first check of
  `initialize_database_pair`). If another process holds a claim exclusively,
  the pair is refused as `database-in-use` with that claim's wait-and-retry
  message, whatever its files look like meanwhile: a pair half created, or a
  restore mid-copy, is not reported as inconsistent, unavailable or missing a
  database, and gets no discard advice. Only a claim file that already exists
  is opened, so classification still writes nothing; every holder creates its
  claim file before it touches a database. Sync planning refuses the same
  way (`Planning refused:`, exit `3`). With three commands started at once on
  a fresh pair, one succeeds and the others exit `3`; the one that created
  the pair may itself be told to retry when a later one holds the claims for
  its own look.
- **Maintenance holds it exclusively** on both databases of the pair, ledger
  first, and refuses rather than waits while any claim is held:
  `hold_maintenance_claims(ledger, history)` releases the ledger claim when
  History's is refused. One gate covers both because a ledger change under a
  History writer still recording location ids is the id-reuse hazard.
  Migration and completion of a one-present pair (`upgrade_database_pair`) and
  each pair maintenance call (`check_database_pair`,
  `backup_database_pair`, `restore_database_from_backup`) hold both claims for
  their whole run and refuse with `database-in-use` otherwise; the db
  operations themselves require their database's held exclusive claim. Schema
  creation (`_create_schema`) takes its own database's claim exclusively before
  SQLite opens the file, so a refused creation leaves no database; pair
  initialization passes it the claim it already holds.
- **Readers take no claim.** SQLite reads are consistent snapshots, and a stale
  view is only behind. Read-only classification (`validate_database_pair`,
  `probe_database_file_contract`, `DatabaseConnectionOwner`) never creates a
  claim file. Admission's second look at a pair it cannot use holds shared
  claims for that look, on claim files that already exist, as below.
- **Where a refusal surfaces.** At admission no run starts. The CLI prints
  `Planning refused:` or `Execution refused:` for sync, or `Inventory refused:`, `Baseline refused:`,
  `Verify refused:` or `Rebaseline refused:`, with the claim's own message
  (`DatabaseMaintenanceActive`, or `DatabaseInUse` on first use), and exits 3. The desktop receives the
  definitive fixed bridge error `database_maintenance`
  ([BRIDGE](BRIDGE.md#fixed-errors)), whose path-free message the page shows
  for Setup inventory, inventory refresh, integrity and execution: no attempt is
  left pending or uncertain, the task keeps its prior state, execution's
  selection is back in review, and the action can be started again once
  maintenance ends. A ledger recorder refusal
  (a session admitted with degraded audit, and inventory acknowledge or
  restore) comes before any
  scan, hash or filesystem change: inventory and integrity end failed with the
  typed error, execution takes its recording-open-failure path, and acknowledge
  or restore raises it to the caller. The CLI then prints the typed error and
  exits 4, still beside the generic recording-degraded lines; the desktop shows
  it as the task's terminal detail, while a visibility batch reports unresolved
  rows without the reason.
- **Tests.** `tests/test_db_claims.py` (real child processes: shared
  coexistence, bounded no-wait refusal, release, killed holders, handle
  inheritance, in-process conflict, path resolution, open and lock failures
  that are not refusals, recorder and observer lifetimes including failed
  closes, schema creation and the pair helper); the live-data guard's view of
  claim creation in `tests/test_live_data_guard.py`; the workflow and
  dispatcher seam, admission refusals on either database, the observer's
  ledger claim against maintenance naming another History and its release,
  and the degraded-audit recorder refusal included, in
  `tests/test_inventory_runtime.py`; the dispatcher's refusal contract in
  `tests/dispatcher/test_dispatcher.py`; the CLI in `tests/test_cli.py`; the
  desktop task starts and fixed bridge error in
  `tests/interfaces/web/test_drain.py` and `tests/interfaces/web/test_transport.py`,
  with the page's handling in the frontend probes.
- **Limits.** A claim is keyed by the resolved main path like SQLite's own
  sidecars, so a hard-link alias of a main file is not covered. The `HistoryStore` writer
  connection opens without a claim; migration's own exclusive file access is
  what refuses it. `reset_databases` deletes files without holding the pair
  claim; only its re-creation takes each database's claim.
- **Outside the gate.** Settings keep their own named mutex. A paused run's
  ledger recorder is closed, but an admitted session's observer holds the
  ledger's and History's shared claims from admission until it closes,
  across pauses, so maintenance cannot run beside held, queued or paused work
  whose audit is healthy. A reviewed plan not yet submitted, a session
  admitted with degraded audit, and a session whose audit degraded after
  admission (the audit pump then closes its observer, releasing both claims,
  while the session lives on) hold neither claim, also while paused. For
  them sync commitments check the ledger instance at start and resume, and
  integrity continuations on resume ([above](#ledger-instance-and-ids)), so
  work that straddles a restore is refused rather than resumed against the
  replacement ledger. Refusing maintenance by naming such waiting work arrives
  with the Data page (M2-B3).

## Data Protection

Status: check, backup, restore and count-based rotation implemented by M2-A4
outcome 4 (2026-11-25) in `namisync/db/maintenance.py`, met for the pair in
`namisync/workflows/database_maintenance.py`. The CLI commands `namisync check`,
`namisync backup` and `namisync restore` are their first consumer (M2-A4
outcome 6; [COMMANDLINE](COMMANDLINE.md#maintenance-commands)); the Data page
follows in M2-B3. Tests:
`tests/test_db_maintenance.py`, `tests/test_database_maintenance.py` (real
child processes: kills per stage, readers, writers, an idle desktop),
`tests/test_cli_maintenance.py` (the commands' output and exit codes, pairs
as found, and the row's closing conditions through the real entry point) and
the restored-at-the-prompt case in `tests/test_cli.py`.

- **The CLI** calls the pair operations below through the service, before any
  database is opened, on the pair as found: it never migrates, completes or
  creates, and it creates no folder. A refusal prints the workflow's own
  guidance, then a closing line decided from the result, and exits `3`.
  `backup-failed` exits `4` from `backup`, but `3`
  from `restore` (the pre-restore backup could not be written, so nothing was
  restored); `restore-failed` and `restore-unconfirmed` exit `4`. `check`
  exits `0` when both roles are `ok` or no database exists at all, and `4`
  for any other state, a missing role included; a folder that does not exist
  is an input error (`2`) unless both are missing.
- **Pointers to the commands.** A damaged database refused at cold admission
  (`DatabaseDamagedError`) and a backup that fails verification because its
  source is damaged both keep their direction to keep the files and add: run
  `namisync check` to see which database is affected, and with a backup made by
  `namisync backup`, `namisync restore <role> <backup file>` replaces it and
  keeps the damaged files beside it. A backup refused for foreign key
  violations names them and gives the same directions. None suggests
  resetting or deleting, or free space, and the admission text stays
  path-free.
- **What changed is the result's, not the text's.** Maintenance refusals and
  failures (restore refusals, the ledger pair rule, `backup-failed`,
  `restore-failed`, `restore-unconfirmed`, `database-in-use`) do not end
  their guidance by saying that nothing changed, and do not name the file a
  call kept: the result carries both (`DatabasePairRestore.kept`,
  `DatabasePairBackup.backups`, the reason). Only a set-aside stopped after
  some sidecars moved names files in its guidance: their new paths, and that
  the database itself is still in place, with no kept file. Admission texts
  shared with other consumers are unchanged.

- **Mechanism.** Each pair call holds both exclusive maintenance claims,
  ledger first, for its whole run, as migration does; there is no dispatcher
  session. Every db operation, rotation included, requires its database's held
  exclusive claim. Every run whose audit is healthy holds the ledger's and
  History's shared claims from admission until its observer closes, so none
  runs beside maintenance ([limits](#maintenance-claim)), new work is refused at admission,
  and no run straddles a moment at which both claims are held. Times are read
  from the clock once both claims are held.
- **Check** reports the pair contract and each role in any pair state. Each
  database is classified without writes (the cold probe), then, for its role
  at the current or older version, `integrity_check` and `foreign_key_check`
  run, at most 20 problems in all. States: `ok`; `foreign-key-violations`
  (admitted, `integrity_check` passes, `foreign_key_check` reports rows, which
  are listed; backup refuses it and restore sets it aside); `missing` (stray
  sidecars are listed); `damaged` (SQLite damage,
  a failed `integrity_check`, or a `-journal` beside the main); `older`;
  `newer`; `wrong-role`; `unsupported` (reset required, such as an old-shape
  schema-5 ledger); `is-backup` (a backup copied into place); `unavailable`.
  Violations found beside another state are listed under it. An `unsupported`
  role's problem says only what was found: which databases a reset discards is
  the pair contract's decision, once the other role is classified.
- **Backup** needs a ready pair and backs up the ledger, then History, at one
  cut time. A read-only connection copies the source with the SQLite backup
  API into an exclusively created temporary beside it, which is switched to
  rollback-journal mode so it stands alone. A ledger copy, and only the copy,
  gains one `backup-cut` row naming its own instance at the cut time. The copy
  is verified (the content check below; the current reader contract, which for a
  ledger must end in exactly `LedgerIsBackup`; every table's row count equal
  to the source's, `ledger_lineage` one more; the cut naming the copy's
  instance), flushed and renamed, never replacing a file, to
  `<main>.backup-<UTC yyyymmddThhmmss + microseconds>Z`. Migration publishes
  through the same helper (`publish_verified_copy`). The source main is never
  written; the read-only connection may leave SQLite's own `-wal` and `-shm`.
  A failure publishes nothing and rotates nothing, with migration's split of
  guidance between a damaged source and write access or free space, and its
  own guidance for foreign key violations; a ledger backup published before
  History's failed is kept and reported.
- **One content check.** Backup verification, restore-source validation and
  restore-image verification apply the same check (`_content_fault`):
  `integrity_check` passes and `foreign_key_check` reports no row. So every
  published maintenance backup is one restore accepts, and a copy restore
  would refuse never enters rotation to displace one it accepts: a database
  with foreign key violations is not backed up (`backup-failed`).
- **Rotation** keeps three backups per database and runs only after both new
  backups are published. Its population is regular files (not links,
  junctions or directories) beside the main named exactly
  `<main name>.backup-<stamp>Z` in that format, ASCII digits only. It keeps the
  new backup by path whatever its stamp, and the newest two others by stamp;
  it never removes or counts either live database main, which a custom path
  may name like a backup of the other role; it reports each failed removal
  and never raises. Migration backups
  (`.backup-v<N>-…`) are never rotated: they are the only way back to 0.1.0
  and restore refuses them. Temporaries, `.replaced-*` sets and every other
  name are left alone.
- **Restore** replaces the ledger or History, one per call, from a backup at
  the current schema; the pair need not be ready. The backup must be a
  standalone regular file (no `-wal` or `-journal` beside it) that passes the
  content check and classifies as a current database of the role, read
  without writes. Refused with nothing changed: `backup-unavailable`,
  `backup-damaged` (failed `integrity_check` or foreign key violations),
  `backup-wrong-role`, `backup-newer`, `backup-unsupported`,
  `backup-older` (v4 and v8 migration backups) and, for a ledger,
  `backup-unstamped` (no `backup-cut` naming its own instance: a hand copy).
  The live database is then checked: a database of another role is
  `target-wrong-role`, sidecars without a main `target-inconsistent`, and an
  unreadable one `restore-failed`, all with nothing changed.
  The image `<main>.restore-<random>.tmp`, created exclusively, is a copy of
  the backup. A ledger image gets a new instance id (`new_instance_id()`) and
  keeps every lineage row, so the backup's own cut becomes its predecessor
  row; History has no lineage. The image is verified (the content check,
  the full current reader contract, so no longer a backup, row counts and
  lineage equal to the backup, the new id in no lineage row) and flushed.
- **The pair rule.** A ledger is restored beside a History in any state but
  two, refused before anything is written: `history-wrong-role` (History's
  path holds another role; the paths look swapped) and `history-newer` (it
  points to the NamiSync that wrote it). A restored ledger never stamps a
  0.1.0 History's runs, since only a ledger the same upgrade call migrated
  from 0.1.0 does ([Ledger instance and ids](#ledger-instance-and-ids)), so a
  damaged, unsupported, unreadable or 0.1.0 History does not block it, and a
  user with both roles damaged can repair either first (user decision,
  2026-11-26). One refusal is advice rather than protection: when the live
  ledger and History both check `older` with no problem listed, a healthy
  older pair that needs updating, the restore is refused with `pair-older`
  and direction to start NamiSync, or run a sync or inventory command, once
  to update the pair, then restore if still needed, because replacing its
  readable ledger with a current-schema backup is almost certainly a
  mistake. Any other ledger target beside an older History, missing or
  damaged included, goes on to the target checks above, which still refuse
  an unreadable one as `restore-failed`. History itself is restored beside a
  ledger in any state: a
  restored History is already stamped, nothing stamps it again, and a ledger
  updated later takes an instance none of its runs carry. A restore beside a
  missing or older database leaves the pair `incomplete` or
  `migration-required` until the next start completes or updates it
  ([One database missing](#one-database-missing)).

  | Restoring | Beside | Outcome |
  | --- | --- | --- |
  | ledger | History `newer` | `history-newer` |
  | ledger | History of another or unknown role | `history-wrong-role` |
  | ledger, itself `older` with no problem | History `older` with no problem | `pair-older` |
  | ledger | History in any other state, or none | restored, after the target checks |
  | History | a ledger in any state, or none | restored, after the target checks |

- **No backup, no change** decides how the image is published:
  - A live database that checks `ok` backs up cleanly. It is
    backed up first, as above but without rotation, so a restore never
    deletes its own source; a failure is `backup-failed` and nothing is
    restored. The SQLite backup API then copies the image into the live main
    as one destination write transaction that commits at its end. The main
    keeps its file, WAL mode, pinned handles and idle connections, so this
    runs beside an idle desktop without exclusive access. Readers keep their
    snapshot until the commit; idle connections read the new content at their
    next transaction, their statements re-prepared; a
    `DatabaseConnectionOwner` still validates, and the runtime's next
    instance read returns the new id, so a plan made before is refused at
    start. A lock refusal between copy steps aborts the copy as
    `database-in-use`, nothing restored. While the copy's transaction is
    open, a new process's cold pair check cannot read the locked part of the
    `-shm` and refuses as `database-unavailable` (exit 3) before admission
    would refuse it; that cold-probe behavior applies to any write
    transaction and predates maintenance.
  - Any other live database (foreign key violations, which no backup of it
    would restore; damaged, older, newer, unsupported, a backup in place, a
    stray `-journal`) needs every other handle closed
    (`require_no_open_handles`, otherwise `database-in-use`), checked before
    any write and again just before the renames. Its `-wal`, `-shm` and
    `-journal`, then its main, are renamed to `<main>.replaced-<stamp>Z` with
    each sidecar keeping its suffix; the set is kept, never deleted. The
    image, converted to the WAL header with no sidecars left (a stray
    `-journal` beside a main is a permanent `inconsistent-pair`), is renamed
    into place.
  - A missing database with no sidecars receives the image by rename.

  No rename replaces a file. A fresh cold read then confirms the current
  contract, every table's row count against the backup (History has no
  instance id, so its counts tell restored content from replaced) and, for a
  ledger, the new id. A failure after the point of no return is
  `restore-unconfirmed` (could not be confirmed; run check), never reported as
  unchanged. Every refusal or failure after the pre-restore backup, or after
  the set-aside main's rename, carries the kept file in the result. A
  set-aside that stops after only sidecars moved keeps no file in the result;
  its guidance names each moved sidecar's new path and says the database
  itself is still at its path. Only temporaries the call created are removed.
- **What a kill leaves** (tested at each stage). In place: the old database
  after the pre-restore backup, after the image is written and mid-copy (the
  uncommitted WAL frames are discarded at the next open), the new one after
  the commit. Set aside: the damaged database while its set is still in place
  or only its sidecars are aside, no database once the main is aside, then the
  new one. Missing: none, then the new one. A rerun finishes from every stage;
  a crash's image temporary stays and is never reused.
- **Limits**, disclosed and not defended under
  [DEFENSE §2.5](DEFENSE.md#25-proportional-defense) and
  [§7](DEFENSE.md#7-quantitative-evidence-and-measurement-authority):
  - The cut is compared as recorded wall-clock UTC, so a clock set back
    across it misplaces runs near it.
  - A kill, or a handle opened in the instant between the sidecar renames and
    the main's, can leave the main in place without its sidecars, and a rerun
    then judges the main alone, splitting the kept set across two stamps. If
    the main alone checks `ok`, the rerun restores in place over it, after
    a pre-restore backup of it, so its own committed `-wal` stays kept under
    the first stamp, apart from the database it belonged to. No file is
    deleted, but that `-wal` is rejoined only by hand.
  - A page-size mismatch between image and live database is SQLite's own
    refusal of the copy, reported as `restore-unconfirmed` although nothing
    changed. A foreign writer holding the WAL lock makes the check read fail
    (`restore-failed`) or, if it takes the lock later, aborts the copy
    (`database-in-use`).
  - Space, a diagnostic and not a measured bound: a restore needs about three
    times the database's size beside it (the pre-restore backup, the image
    and the copy's WAL); beside an idle desktop the WAL is not checkpointed
    and the confirming cold read copies the main and that WAL to a private
    snapshot, so the peak is higher. Running out of space at confirmation
    reports `restore-unconfirmed` after a completed restore.
  - A plain file copy of a ledger put back by hand keeps its instance and
    cannot be detected; only a backup copied into place is refused.

Still accepted but unrealized: detail retention must use a writable
connection and canonical time comparison, preserve summaries when pruning
detail, and remain idempotent. An optional second-volume backup requires its
own custody. Export/import validate versions and never overwrite the live
database without a verified backup and atomic replacement path. Trash
retention is filesystem-domain maintenance but uses ledger/history evidence
and capacity planning; undo creates an ordinary reviewed plan.

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
