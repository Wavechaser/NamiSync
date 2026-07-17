# Inventory Domain

Status: draft cross-module contract. Priority: M1. Inventory is not a new
sideways-calling operation module: scanner observes, workflows coordinate, and
database repositories/recorder retain state.

## Purpose

Inventory is the durable, role-free record of what has been observed at a
physical location and what integrity evidence exists. A location may exist with
zero, one, or many mappings. Inventory state must not be reinterpreted by plan
view state, mapping role, UI filters, or a partial scan.

## State Model

Each row belongs to one physical location and has canonical/display relative
path, present/missing/unsupported state, latest safe observation, optional hash
and provenance, hash-observed/last-verified times, missing acknowledgement,
reappearance marker, host provenance, and optional hardlink group.

Mapping correspondence is separate and mapping-scoped. A shared location keeps
one physical inventory while each mapping retains independent source/target
relationship evidence.

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

## Location And Mapping Guidance

Repository reads return zero/one/many mapping associations. Workflows require
explicit paired roots when association is ambiguous. Known drive-letter changes
resolve through volume evidence; rebinding to a different location/volume is an
explicit sampled verification workflow. Cloned-volume ambiguity is never
auto-resolved.

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
- Complete rescan marks only truly unseen in-scope rows missing and preserves
  their hash/stat evidence.
- Incomplete scan and offline volume mark no unseen row missing.
- Scoped refresh changes only requested keys and performs bounded queries.
- Returning missing rows become reappeared; matching verify or explicit
  baseline clears reappearance atomically.
- Acknowledgement/restore changes visibility state without deleting evidence.
- Mapping filters preserve physical rows and cannot turn exclusions into target
  deletion candidates.
- Hashed baseline stats are not overwritten by ordinary observation of modified
  content; verifier classifies it `modified`.
- A location with >33k files reconciles without SQL variable overflow and with
  bounded transaction/round-trip behavior.
- Mapping-state foreign keys/composite checks reject target rows from another
  location.
- Drive-letter change resolves the same known volume; label change follows the
  finalized DR-10 rule; simultaneous clone ambiguity requires a choice.
- Inventory queries expose zero/one/many mappings without guessing.
- UI filtering and Plan invalidation cannot clear or mutate inventory state.

