# Inventory Domain

Status: the M1 role-free inventory workflow, three-shape scoped reconciliation,
acknowledgement/restore, typed queries, standalone integrity selection, and the
Stage 5.5 recursive scan-scope foundation are implemented. Inventory is not a new
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
observations. A complete online `FULL` scan uses a temporary observed-key table
to mark unseen present/unsupported rows missing without a parameter-sized
`NOT IN`. Exact `PATHS` reconciliation affects only named keys. `SUBTREES`
reuses the observed-key anti-join but bounds it to the union of remaining exact
paths, each root equality, and each root's literal canonical descendant range.
Incomplete and offline scans infer no missing state. Reappearance is set on a
missing-to-present or missing-to-unsupported transition.

`LedgerRepository` returns immutable typed rows and bounded canonical-path
selections. Every multi-batch selection stays in one read transaction so a
concurrent inventory commit cannot produce a torn result. The conditional
integrity recorder writes attestation and optionally clears
`reappeared_at`/advances true verification time in the same transaction.
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

Inventory continuation payloads are strict version 2 because they carry
`subtree_roots` separately from exact `selected_paths`. Integrity continuations
remain version 1 because folder actions freeze indexed descendants into the
existing exact-subject shape before admission. Their shared decoder validates
the exact field set and JSON scalar types, rejects duplicate object keys, and
checks kind and expected version independently. Inventory and integrity details
retain the scanner's typed warnings; an incomplete refresh therefore preserves
the warning code, relative path, and detail rather than reporting only
`complete=False`.

Every incomplete full or stale-scope integrity refresh refuses before hashing.
An exact integrity pre-scan may continue only when all incompleteness is
explained by warning-backed unreadable frozen subjects. Those rows enter the
verifier once as `unsupported`, receive no attestation, and keep the integrity
result incomplete without suppressing readable siblings. An ignored subject, a
root/global warning, cancellation, or any other unaccounted scope gap still
refuses before hashing.

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

- `PATHS` observes and reconciles only requested canonical keys; an exact
  directory row never implies anything about its children. A completed exact
  observation marks an absent prior `present` or `unsupported` subject missing.
- `SUBTREES` recursively observes each canonical root and may retain exact paths
  outside the roots in the same session. Overlapping roots and covered exact
  paths are removed by segment-aware normalization; selecting the location root
  becomes `FULL`.
- Completed subtree missing inference covers prior `present` and `unsupported`
  rows at each root and below it. It uses the default-binary range
  `>= root || '\' AND < root || ']'` plus a separate equality, never `LIKE`, so
  `%`, `_`, and `]` remain literal filename characters.
- Already-missing and out-of-scope rows remain byte-for-byte unchanged. One
  incomplete root conservatively withholds missing inference for the whole
  mixed scope while retaining safe observations and typed warnings.

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
- Exact and recursive scoped refreshes take distinct branches, change only
  their declared union, and perform bounded indexed queries.
- Nested and hostile-name subtree fixtures prove canonical keys and literal
  missing ranges; incomplete, absent, unavailable, and now-file roots preserve
  their distinct reconciliation outcomes.
- Inventory v2 and integrity v1 payloads round-trip and reject wrong versions
  and wrong workflow kinds independently.
- Incomplete inventory details retain typed scan warnings, and unreadable
  frozen integrity subjects do not suppress readable siblings.
- Returning missing rows become reappeared whether the new observation is
  `present` or `unsupported`; matching verify or explicit baseline clears
  reappearance atomically.
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
