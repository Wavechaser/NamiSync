# Inventory Domain

Status: the M1 role-free inventory workflow, scoped reconciliation,
acknowledgement/restore, typed queries, and standalone integrity selection are
implemented. Inventory is not a new
sideways-calling operation module: scanner observes, workflows coordinate, and
database repositories/recorder retain state. The Stage 5 CLI exposes explicit
location inventory and integrity starts through the shared service; desktop
actions remain Stage 6.

## Purpose

Inventory is the durable, role-free record of what has been observed at a
physical location and what integrity evidence exists. A location may exist with
zero, one, or many mappings. Inventory state must not be reinterpreted by plan
view state, mapping role, UI filters, or a partial scan.

## Implemented Inventory Slice

The ledger schema stores current observation fields separately from attested
hash subject fields, including nullable identity/hardlink-group room, presence,
unsupported reason, missing/acknowledgement/reappearance timestamps, host
provenance, and scope token. Ordinary scans update only current observation
fields and cannot rewrite an established attestation.

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
baseline/verify/rebaseline (pause supported), and the CLI reaches all four only
through the shared service. A fresh baseline selection admits eligible
non-directory rows without evidence; a fresh rebaseline selection admits only
rows with evidence; verify retains both. Integrity continuation stores the
exact admitted inventory row ids plus completed ids/bytes. A resume always
refreshes physical inventory but reconstructs the original ordered candidate
set without reapplying those mode filters, so evidence drift cannot drop
pending work and a newly appeared row cannot enter an admitted session.

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

Mapping correspondence is separate from role-free inventory. A shared location
keeps one physical inventory while each mapping retains independent accepted
source/target relationship evidence.

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

### Offline and visibility states

An unmounted volume is offline, not a location full of missing files.
Acknowledging missing hides it from the default view but does not delete
evidence; restore reverses only acknowledgement.

## Location And Mapping Guidance

Repository reads return zero/one/many mapping associations. Workflows require
explicit paired roots when association is ambiguous. Known drive-letter changes
resolve through `VolumeId(serial, fs_type)`; label changes are noted without
rebind, a matching serial with changed filesystem type requires explicit rebind,
and simultaneous duplicate identities require explicit user choice. Rebinding
to a different location/volume is an explicit sampled verification workflow.

The CLI selects exactly one positional root or `--location-id`; it never treats
a numeric root as an id or infers a location from a mapping. Repeatable
`--path` supplies an exact root-relative scope. If cloned volume identities
produce multiple mounted candidates, the refusal lists them and requires an
explicit `--mount` retry. Offline, missing-root, and unavailable-root states
perform no missing reconciliation and give state-specific recovery guidance.

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
  observation shape regardless of mapping associations.
- Complete rescan marks only truly unseen in-scope rows missing and preserves
  their hash/stat evidence.
- Incomplete scan and offline volume mark no unseen row missing.
- Scoped refresh changes only requested keys and performs bounded queries.
- Returning missing rows become reappeared; matching verify or explicit
  baseline clears reappearance atomically.
- Acknowledgement/restore changes visibility state without deleting evidence.
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
- Interface starts require one explicit root/id and an explicit listed mount
  for clone ambiguity; both database overrides remain composition inputs.
- Fresh mode filtering and frozen-resume selection preserve original admitted
  order, completed ids/bytes, and the original row set.
- UI filtering and Plan invalidation cannot clear or mutate inventory state.
