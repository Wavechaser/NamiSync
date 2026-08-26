# Inventory Domain

Status: the M1 role-free inventory workflow, three-shape scoped reconciliation,
acknowledgement/restore, typed queries, standalone integrity selection, and the
Stage 5.5 recursive scan-scope foundation are implemented. Inventory is not a new
sideways-calling operation module: scanner observes, workflows coordinate, and
database repositories/recorder retain state. The Stage 5 CLI exposes explicit
location inventory and integrity starts through the shared service; desktop
actions remain Stage 6. The Setup admission, remembered-location, cached-
projection, ledger-current evidence, and manual-handoff contracts below are
accepted Stage 6 targets and are not active until their implementation gates
close.

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
or hash work at initial start, resume, and queued wakeup. The resolver-selected
mount is supplied to core's chain-only root admission; that admission performs
no new volume observation, preserves the lexical path in workflow details, and
still precedes the separate accessibility probe. If any component in the
configured root path
below its reviewed volume mount becomes a junction, symlink, placeholder, or
other reparse point, resolution returns `root_unavailable` before probe,
reconciliation, missing inference, or integrity hashing; the reviewed mount
itself is the excluded trust anchor, and matching volume identity alone never
authorizes a redirected tree. When that stable volume is legitimately mounted
at one new path, resolution carries the current selected mount—not the stale
stored hint—as the scanner and verifier trust anchor. When the configured root
equals that selected folder mount, FULL scanning admits the anchor's own
mount-point classification only under matching current mount and full-volume
binding; no component below it inherits the exception.

The production dispatcher registry contains inventory (pause unsupported) and
baseline/verify/rebaseline (pause supported), and the CLI reaches all four only
through the shared service. In the current implementation, a fresh baseline
selection admits eligible non-directory rows without evidence; a fresh
rebaseline selection admits only
rows with evidence; verify retains both. Integrity continuation stores the
exact admitted inventory row ids plus completed ids/bytes. A resume always
refreshes physical inventory but reconstructs the original ordered candidate
set without reapplying those mode filters, so evidence drift cannot drop
pending work and a newly appeared row cannot enter an admitted session.
Fresh full, selected-path, and stale candidate reads apply their eligibility in
SQL and admit at most 120,000 unique rows. The reconstruction queries only
location-owned row IDs in 400-ID chunks under the same repository read snapshot;
it does not materialize the complete location and preserves the frozen order.
Foreign or missing saved identifiers refuse rather than widening selection.
Stale-before integrity unions exact completed rows with eligible stale rows by
identity before enforcing the count, so an overlap is charged once. An excess
after successful refresh is `FAILED+RAN`, publishes no partial selection, and
starts no verifier work; a recorder finalization failure retains error
precedence. Accepted rows share one root `Path` owner rather than copying it per
candidate. The independent retained-byte axis remains inactive until the
checkpoint-4 graph model freezes its complete charge.

Checkpoint 10 will admit eligible null-evidence files to fresh rebaseline as
well. It remains explicit acceptance of current content: always hash and
conditionally replace/create evidence, even on a genuine match, and clear
verification freshness. Compare-and-accept is deferred beyond M1. The
[verifier policy table](VERIFIER.md#standalone-operation-policy-checkpoint-10-target)
distinguishes the three operations and current versus accepted behavior.

Desktop rebaseline requires explicit acknowledgement of current evidence;
baseline and verify do not. The bridge owns the exact receipted request shape
and rejects a mismatched intent before scope, ledger, or native work.

Inventory continuation payloads are strict version 2 because they carry
`subtree_roots` separately from exact `selected_paths`. Integrity continuations
independently advance to strict version 2 so a pause retains its physical-read
total high-water and aggregate recording status beside the exact frozen
subjects. Their shared decoder validates the exact field set and JSON scalar
types, rejects duplicate object keys, and checks kind and expected version
independently. Inventory and integrity details retain the scanner's typed
warnings; an incomplete refresh therefore preserves the warning code, relative
path, and detail rather than reporting only `complete=False`.

Every incomplete full or stale-scope integrity refresh refuses before hashing.
An exact integrity pre-scan may continue only when all incompleteness is
explained by warning-backed unreadable frozen subjects. Those rows enter the
verifier once as `unsupported`, receive no attestation, and keep the integrity
result incomplete without suppressing readable siblings. An ignored subject, a
root/global warning, cancellation, or any other unaccounted scope gap still
refuses before hashing.

## Stage 6 Desktop Contracts (Protocol Subset Active)

Exact Setup admission, recents, bridge wire shapes, paging, hard walls, scalar
domains, and retention accounting are centralized in
[M1_BRIDGE.md](M1_BRIDGE.md), with safety classification in
[DEFENSE.md](DEFENSE.md). Inventory consumes the shared workflow-owned location
candidate pipeline and always re-admits a real start; a slot or
`RootAuthority` is evidence, never cached authorization.

Checkpoint 3.2 activates the signed-64 scalar, full-width native identity, and
event/persistence epoch consumed here. Setup, recents, desktop projection,
paging, and retention behavior below remain inactive until their named
checkpoints.

The desktop inventory projection is one canonical server-side view over a
complete immutable inventory generation. Search, filters, collapse, visible
order, action scope, and windows all derive from that projection; the browser
does not reconstruct hierarchy or scope from paths or its current page.
Projection eviction removes only rebuildable view state. A refused refresh
stages no partial artifact and preserves the prior inventory generation and its
view identity unchanged.

Checkpoint 9 adds the shared server-owned sibling sorter from
[Bridge DR-BR-15](M1_BRIDGE.md#sibling-sorting-accepted-checkpoints-7-and-9).
New views and reset use canonical path-key order; filename, size, and mtime
are explicit opt-in column/direction choices. Sort the complete projection
before windowing, using raw own-object values, deterministic ties, and
unavailable values last. A real folder may expose its own observed mtime;
synthetic ancestors have no invented descendant-derived time. Sorting changes
only presentation/view state, never selection, recursive action scope,
integrity candidate order, or execution authority. Full production bridge
support and raw mtime facts land even if their GUI layout remains latent.
Status/progress sorting, global flat sorting, and durable preferences are not
M1 work. H2 9.A owns regression, race, and scale acceptance.

Warning rows are informational leaves, not inventory subjects. They have typed,
stable identities and attachment order, but never enter the canonical path
index, domain subtree membership, rollups, or action-scope resolution. Detail,
acknowledge/restore, refresh, and integrity commands reject a warning target
before ledger or native work. Folder rollups cover domain descendants only and
are independent of filtering and acknowledged-row hiding; checked byte
accumulation reports overflow rather than clamping.

Each inventory row keeps two orthogonal facts: ledger-derived
`verification_state` and the latest ordinary-integrity overlay. Replacing an
ordinary-integrity generation cannot rewrite execution or manual post-copy
truth. Live overlays reconcile through the frozen workflow-item-to-domain-node
map; unknown or duplicate alignment is structural failure, never a path join.
The exact overlay and replacement protocol is owned by the bridge plan.

File detail exposes current durable ledger evidence. Execution evidence is a
separate atomic-read projection over the original execution scope; it does not
turn a plan row into hash storage or reinterpret ordinary integrity state.
[VERIFIER.md](VERIFIER.md) owns how eligible durable evidence becomes a manual
exact post-copy handoff, while [DATABASE.md](DATABASE.md) and the bridge plan
own the exact join and wire classification.

## State Model

Each row belongs to one physical location and has canonical/display relative
path, present/missing/unsupported state, latest safe observation, optional hash
and provenance, hash-observed/last-verified times, missing acknowledgement,
reappearance marker, host provenance, and optional hardlink group.
Rows with retained content evidence also carry an optional sticky verification
invalidation (`metadata-drift` or `hash-mismatch`). The derived presentation
state is `unverified`, `verified`, `modified`, or `mismatched`; it never infers
current verification from a historical `last_verified_at` alone. For a present
row with current observation and attestation, sticky `hash-mismatch` is
projected before ordinary stat/identity drift, so later metadata change cannot
downgrade the visible state to merely `modified`.

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
records. If current kind/size/mtime or a known identity diverges, reconciliation
sets a sticky invalidation marker while retaining the prior attestation for
comparison and recovery. Later matching metadata does not clear that fact, and
a known hash mismatch dominates metadata drift until a successful evidence
write clears or replaces it.

Integrity runs bind each native file open to the resolver-selected mount and
the location's full `VolumeId`. The verifier rechecks that authority before
each open and requires the opened handle to corroborate the expected volume
serial before any bytes can become baseline or verification evidence.

## Reconciliation

### Complete location scan

- Upsert safely observed present/unsupported entries in batches.
- Preserve established evidence unless a conditional evidence workflow changes
  it; mark evidence invalid when the new observation contradicts its attested
  subject.
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
and true verification, plus any durable invalidation or current/attested
contradiction. Queries include invalidated rows regardless of verification age
without changing them. Selecting stale rows constructs a verifier selection;
inventory itself does not hash in the background.

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
