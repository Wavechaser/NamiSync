# Inventory Domain

Status: the M1 role-free inventory workflow, scoped reconciliation,
acknowledgement/restore, mapping-scoped filter persistence, typed queries, and
standalone integrity selection are implemented. Inventory is not a new
sideways-calling operation module: scanner observes, workflows coordinate, and
database repositories/recorder retain state. CLI/UI commands remain deliberately
unexposed until the later interface stage.

## Purpose

Inventory is the durable, role-free record of what has been observed at a
physical location and what integrity evidence exists. A location may exist with
zero, one, or many mappings. Inventory state must not be reinterpreted by plan
view state, mapping role, UI filters, or a partial scan.

## Implemented Inventory Slice

The ledger schema stores current observation fields separately from attested
hash subject fields, including nullable identity/hardlink-group room, presence,
unsupported reason, missing/acknowledgement/reappearance timestamps, host
provenance, and scope token. Mapping exclusion projection timestamps live in
their separate mapping-scoped table. Ordinary scans update only current
observation fields and cannot rewrite an established attestation.

`LedgerRecorder.record_inventory()` batches present, directory, and unsupported
observations. A complete online full scan uses a temporary key table to mark
unseen present/unsupported rows missing without a parameter-sized `NOT IN`;
incomplete and offline scans infer no missing state, while complete selected
refreshes affect only selected keys. Reappearance is set on a missing-to-present
transition.

`LedgerRepository` returns immutable typed rows and bounded canonical-path
selections. The conditional integrity recorder writes attestation and optionally
clears `reappeared_at`/advances true verification time in the same transaction.
Acknowledgement/restore changes only visibility state, while stale-age queries
select candidates without mutating them.

The inventory workflow re-resolves stable volume identity before each
invocation, registers first locations in the exact order host -> volume
observation -> role-free location -> scan -> inventory recording, and
never creates a mapping from location-only activity. Resolution preserves five
distinct outcomes: `resolved`, `offline`, `ambiguous`, `root_missing`, and
`root_unavailable`. Ambiguity requires an explicit choice before submission;
a changed candidate set (including a newly mounted clone) refuses before scan
or hash work at initial start, resume, and queued wakeup. Native root stat and
probe calls preserve the logical path in workflow details while delegating
extended-length conversion and directory access to the long-path-safe scanner
boundary.

The production dispatcher registry contains inventory (pause unsupported) and
baseline/verify/rebaseline (pause supported), although no CLI/UI start command
is exposed yet. Integrity continuation stores the exact admitted inventory row
ids plus completed ids/bytes. A resume always refreshes physical inventory but
hashes only the original candidate set, so a newly appeared row is retained
without being swept into an already admitted session.

## State Model

Each row belongs to one physical location and has canonical/display relative
path, present/missing/unsupported state, latest safe observation, optional hash
and provenance, hash-observed/last-verified times, missing acknowledgement,
reappearance marker, host provenance, and optional hardlink group.

Present files retain `MetadataSnapshot` attributes and creation time needed by
reviewed preservation. Every walked directory has a `DirRecord`, and typed
`UnsupportedRecord` observations remain distinguishable from ordinary files;
unsupported state is never reconstructed from warning text. ADS is not
inventory state: the deferred feature enumerates streams only in the executor.

Mapping correspondence and filtering are separate and mapping-scoped. A shared
location keeps one physical inventory while each mapping retains independent
source/target relationship and filter evidence. `mapping_filters` is the
authoritative current `FilterSet`; planner-facing reads evaluate it
deterministically for every row. `mapping_exclusions(mapping_id, inventory_id)`
is only a snapshot-hash-tagged cache/audit projection. A stale projection is
reported through typed snapshot state and never overrules the current filter.

Hashed rows preserve the stat unit that the hash attests. A later ordinary scan
must not overwrite those baseline stats merely to reflect current modified
content; current observation and retained attestation are distinct fields or
records.

## Reconciliation

### Complete location scan

- Upsert safely observed present/unsupported entries in batches.
- Preserve established evidence unless a conditional evidence workflow changes
  it.
- Mark previously present unseen rows missing only when the scan is complete for
  that location/ignore scope and the volume is online.
- Preserve prior metadata/hash when marking missing.
- Mark returning rows reappeared until matching evidence or explicit baseline
  resolves them.
- Never create/infer mapping roles from a location scan.

### Scoped refresh

- Observe and update only requested canonical keys.
- A requested absent path may be marked missing if its parent/root observation
  is authoritative for that exact path.
- Unrequested rows retain state; no location-wide missing sweep runs.

### Offline and filtered states

An unmounted volume is offline, not a location full of missing files. Mapping
filters mark rows excluded from that mapping view while preserving physical
inventory evidence. Acknowledging missing hides it from the default view but
does not delete evidence; restore reverses only acknowledgement.

Complete filter replacement evaluates every current row in both mapping
locations. The recorder rechecks that exact identity coverage inside the same
writer transaction before replacing the filter and both projections, closing
the inventory-row race. A role-free refresh never updates mapping policy; new
or untouched rows are classified dynamically until a later projection refresh.

## Location And Mapping Guidance

Repository reads return zero/one/many mapping associations. Workflows require
explicit paired roots when association is ambiguous. Known drive-letter changes
resolve through `VolumeId(serial, fs_type)`; label changes are noted without
rebind, a matching serial with changed filesystem type requires explicit rebind,
and simultaneous duplicate identities require explicit user choice. Rebinding
to a different location/volume is an explicit sampled verification workflow.

## Expectations Of Other Modules

- Scanner supplies observations and completeness/scope, but writes nothing.
- Recorder/repositories own transactional reconciliation and reads.
- Verifier consumes immutable selections and conditionally updates evidence.
- Planner receives separate mapping correspondence, not raw role assumptions.
- Interfaces keep Plan and Inventory caches/views separate and disclose scope.
- Ingest does not create source inventory; its destination may be a tracked
  library location and receives origin annotations only after copy success.

## Evidence Staleness

Staleness derives from injected UTC timestamps for observation, hash creation,
and true verification. Queries can filter older-than cutoffs without changing
rows. Selecting stale rows constructs a verifier selection; inventory itself
does not hash in the background.

## Latent Features

Shared network inventory requires explicit host authority/merge semantics and
is deferred. Hardlink grouping uses the nullable schema field without enabling
move or preservation automatically. Tombstone pruning requires an impact
summary and policy; missing acknowledgement is not pruning.

## PoC Hardening

- Role-free locations fix the single-sided baseline design gap.
- Complete/scoped/offline distinctions prevent false missing state.
- Separate attested versus current stats prevent edited files becoming false
  mismatches.
- Batched writes/reads avoid per-file round trips and SQLite parameter limits.
- Canonical keys prevent casing/separator wrong-target actions.
- Mapping/location composite constraints prevent a correspondence pointing at
  an unrelated location.

## Acceptance Criteria

- A first complete scan creates one role-free location and deterministic rows
  without creating a mapping.
- Complete scans retain every walked directory and one canonical role-free
  observation shape regardless of mapping policy.
- Complete rescan marks only truly unseen in-scope rows missing and preserves
  their hash/stat evidence.
- Incomplete scan and offline volume mark no unseen row missing.
- Scoped refresh changes only requested keys and performs bounded queries.
- Returning missing rows become reappeared; matching verify or explicit
  baseline clears reappearance atomically.
- Acknowledgement/restore changes visibility state without deleting evidence.
- Mapping filters preserve physical rows and cannot turn exclusions into target
  deletion candidates.
- Two mappings sharing one physical location may exclude the same row
  differently; a new row and an inverse filter change take effect immediately
  without stale projection policy.
- Hashed baseline stats are not overwritten by ordinary observation of modified
  content; verifier classifies it `modified`.
- A location with >33k files reconciles without SQL variable overflow and with
  bounded transaction/round-trip behavior.
- Mapping-state foreign keys/composite checks reject target rows from another
  location.
- Drive-letter/label change resolves the same known volume; filesystem-type
  change requires rebind; simultaneous clone ambiguity requires a choice.
- Offline, ambiguous, missing-root, and unavailable-root outcomes perform no
  scan and mark no retained row missing; only `resolved` reconciles.
- Inventory queries expose zero/one/many mappings without guessing.
- UI filtering and Plan invalidation cannot clear or mutate inventory state.
