# Planner Module

Status: M0 path-preserving paired-sync implementation complete. M1 Stage 1
removes the unused worker-count field from the immutable plan contract.
Stage 5.5 relocates the planner's three relative hierarchy helpers to
`core.pathing` without changing planning behavior. Later scopes, content
evidence, ingest policies, replay, repair, and undo reuse the same plan shape.
The signed-64 scalar boundary is active from Stage 6 checkpoint 3.2, and the
pre-model planning-source admission is active. The complete Setup snapshot and
complete task-artifact retained-graph contract below remain accepted targets
until their implementation checkpoints close. The
100,000-operation shape is a performance fixture, not the production maximum.

## Purpose

The planner is a pure deterministic transformation from immutable evidence and
policy snapshots to an immutable `Plan`. It decides intended operations and
dependencies; it never touches the filesystem, writes a database, asks a human,
or executes/repairs anything.

## Required Inputs

```python
plan(source: ScanResult, target: ScanResult,
     correspondence: MappingSnapshot, options: SyncOptions,
     scope: Scope, *,
     review_admission: PlanReviewAdmission | None = None) -> Plan
```

## Implemented M0 Surface

`namisync.modules.planner.plan()` is a pure transformation over frozen core
snapshots. `namisync.core.planning` owns the serializable plan, operation,
assignment, policy, scope, deterministic-id/fingerprint, selection-digest,
and shared capacity contracts. M0 implements `Scope.everything()` and the
batch-shaped identity destination policy; the other scope constructors remain
declared but raise rather than pretending to work.

Depth ordering, parent walks, and strict descendant checks use the shared
relative-path helpers in `namisync.core.pathing`. Their Stage 5.5 promotion was
a pure relocation: the existing planner test file and all 31 behavioral tests
remain unchanged.

The implementation emits explicit parent-first directory operations, file
copy/update/no-op intent, correspondence-qualified move or composite
move-update intent, target-only policy operations, and dependency-ordered
directory cleanup. Blocked unsupported/collision items remain in the plan.
Planner and preflight both call `calculate_required_bytes()`; neither stores or
guesses target free space.

`options` contains deletion and preservation policies, the symmetric mapping
filter snapshot, the selected `DestinationPolicy`, and the fingerprinted
`propagate_source_casing` policy plus any already-extracted enrichment metadata.
The casing policy defaults to false and is exposed through the primitive
semantic-settings facade; there is no current settings CLI or GUI control.
`MappingSnapshot` contains prior accepted pairs/no-ops, retained missing rows,
and ambiguity/hardlink disqualifiers keyed by canonical path. Observed target
free space is deliberately absent: review and execution call `observe()` and
judge the same pure required-byte formula against current space.

The Stage 6 adapter supplies one backend-canonical frozen Setup snapshot. The
workflow translates its planning fields into immutable `SyncOptions`; linked
verification remains workflow/session policy rather than planner input.
Planner never rereads settings or accepts a parallel execution-time choice.
The exact Setup and filter contracts are owned by
[M1_BRIDGE.md](M1_BRIDGE.md).

No input may be fetched from SQLite, settings, clock, or filesystem inside the
planner.

Planning workflow supplies already-detached scans and one exactly captured
correspondence result. Planner revalidates their declared contract, captures
the destination-policy identity and callback, and gives that nested hostile
callback only detached filtered `FileRecord`s plus a detached target scan. Its
returned assignment is source-gated and reconstructed exactly once. The four
raw mapping populations and the combined operation population each have
independent stateless first-excess gates; no mapping index, operation builder,
dependency sort, or callback-input copy is charged as retained state.

Workflow reconstructs the hostile planner result with exact constructors and
contract validators. Canonical `plan_fingerprint(snapshot)` revalidation uses
the existing complete semantic projection to reject hostile field drift; that
validation belongs to the exact-snapshot prerequisite, while this source wall
does not charge or freeze the projection's construction cost. Workflow then
charges the final operation rows and only the unavoidable operation/dependency,
assignment, and required-volume shallow slots once. Selection remains ordinary
workflow policy and is neither copied nor charged by this prerequisite. First
excess raises the shared typed review-limit error without publishing a partial
plan.

Review-limit authority belongs to the workflow's current admission family;
planner receives one zeroed member. Planner logical-byte accumulation and
candidate revalidation issue their limit through that member. Destination
policy has no such authority: its identity, assignment, or unreviewed
fingerprint error propagates unchanged from a direct planner call and workflow
classifies an unissued review-limit signal as ordinary failure. Reviewed
fingerprinting uses the one captured policy identity instead of rereading
hostile policy properties.

Checkpoint 4 must eliminate or finitely charge ordinary escapes from
`snapshot_plan_options`, `plan`, and `snapshot_plan_candidate`. Property,
assignment, fingerprint, and validation failures can retain stage-dependent
policy, callback, detached scan/file, and input frames through public unwind.
Preserve their existing public type, identity, and behavior.

Those counters establish the planning-source wall, not the checkpoint-4
complete retained-graph model. Policy and planning construction temporaries,
sorting/index storage, selection and preview values, additional complete-tree
projection, generic container allocation, serialization/codec copies, native
views, browser copies, and task retention require the later predeclared
reservation model and independent validator.

Core policy admission bounds the raw shape before canonicalization. A filter
snapshot is an exact tuple of at most 64 nonempty valid-Unicode patterns, each
at most 1,024 UTF-8 bytes and together at most 16,384 bytes. An assignment is
an exact tuple of at most 120,000 typed items. Destination-policy name/version
and optional group/conflict annotations have no narrower production grammar;
each value is capped by the plan-domain ceiling, and the complete combined
occurrences still require the checkpoint-4 publication graph admission.
Constructors and policy/assignment validators revalidate these contracts so
forged frozen fields do not bypass them.

## Plan Contract

A plan snapshots roots and `VolumeId` evidence, complete-scan state, filters,
semantic options, `PreservationPolicy`, policy/version fingerprint,
deterministic operations, dependency graph/order, required volumes, required
content bytes, concurrency assumption, and all source/target stat evidence
needed by preflight. It contains no target-free-space observation.

A plan also contains no content hash, copy-stream attestation, verification
digest, or ledger evidence classification. Those values cannot affect dry-run
intent and are queried from current ledger state only by later execution or
inventory detail surfaces.

Each operation has a stable id derived from canonical intent—not list position
or random state—and includes kind, source/target relative paths, expected
before-state, intended after-state, byte contribution, reason code,
dependencies, and blocked/conflict detail. Execution never recomputes target
paths or destination policy. Expected/intended metadata uses
`MetadataSnapshot` (attributes and creation time) under the snapshotted
preservation policy. No stream manifest enters a plan.

Plan and operation hashes use explicit complete field projections rather than
generic dataclass traversal. `plan_fingerprint()` omits only the plan's own
fingerprint; public `serialize_plan()` includes it. Non-null file indices use
canonical quoted `FileIndex128` text, while sizes, timestamps, and other integer
fields retain their numeric form. Sequence order and the established canonical
JSON ordering of required-volume sets remain unchanged. Policy hashing keeps
the destination policy's intentional name/version projection, not its private
implementation state. Unsupported objects or keys and nonfinite numbers refuse
at the shared closed JSON boundary described in [CORE.md](CORE.md).

Checkpoint 3R.14 changes identity-bearing hashes under the shared epoch-6
cutover; frozen identityless plan bytes remain identical. Plan-v5 and
execution-v6 workflow wire shapes are unchanged. Existing workflow
refingerprinting rejects an old numeric-identity fingerprint before execution,
while unchanged identityless fingerprints remain compatible; database reset
does not silently rewrite old commitments.

Valid Unicode strings retain their established UTF-8 encoding, including
supplementary characters and literal backslash text. Malformed surrogate code
units in any hash input or key refuse at strict serialization; they are not
silently rewritten into a different decoded value. Scanner path validation and
optional warning-detail omission remain separate admission rules described in
[CORE.md](CORE.md).

`ExecutionSet` selects a dependency-closed subset and carries per-operation
status. Its optional `Commitment` binds both the plan fingerprint and a
deterministic digest of that exact selection; changing either invalidates the
commitment. Workflow derives M0's safe subset from the full plan: direct
blockers stay `BLOCKED`, correspondence/dependency exclusions stay `DEFERRED`,
and incomplete scans withhold destructive/identity operations. Planner itself
continues to emit complete deterministic intent and does not hide those items.
That split is deliberate: a blocked parent/type conflict or unsupported source
row remains reviewable alongside the raw policy removal the target-only diff
would otherwise request. `derive_execution_selection()` quarantines the
same-correspondence removal and blocked dependencies before preflight/execution,
while unrelated safe work remains selectable. Interfaces therefore show full
intent but can execute only the derived safe selection; they must not treat raw
`Plan.operations` as executable authority.

## Diffing And Operation Rules

- Compare through `DestinationPolicy.assign()`, including the M0 identity
  assignment; never directly assume source path equals target path.
- Apply the plan's filter snapshot symmetrically before diffing. Location
  ignores have already bounded scan completeness.
- Compare mtimes within the coarser capability granularity.
- Matching size, mtime within the coarser granularity, and the shared managed
  attribute subset (readonly, hidden, system, and not-content-indexed) is an M0
  metadata no-op. Drift in any managed bit plans an update even when size and
  mtime are unchanged. Raw unmanaged bits such as ARCHIVE and TEMPORARY remain
  in both reviewed snapshots but do not schedule work the executor does not
  propagate. Content-aware no-op comes later.
- Source-only files plan copy; changed matched files plan update.
- Every directory the plan will create has an explicit parent-first
  mkdir-with-metadata operation; file and child-directory operations depend on
  their parent mkdir. Executor never creates an implicit parent.
- Target-only files/directories follow additive/trash/internal-mirror policy.
- Directory cleanup reasons about removals planned in this same plan, not only
  the pre-scan tree.
- Same-side case collisions and file/directory collisions become blocked
  operations with no guessed winner.
- A single source and target file that share a Windows path key but differ in
  exact spelling retain the normal metadata result: changed content plans an
  update and matching metadata plans a no-op. The typed `case_mismatch` reason
  is a non-blocking review advisory. By default the operation preserves the
  target's observed spelling. The captured `propagate_source_casing=True` policy
  instead emits a zero-byte `recase` operation when metadata already matches,
  carrying both observed and requested spellings for a same-volume rename. If
  content metadata changed, the required update also publishes at the requested
  spelling. Recasing does not create a trash version, rewrite content, or recase
  parent directories; a distinct occupied case-sensitive destination is refused
  by the non-replacing rename rather than overwritten.
- A one-to-one source/target file pair in the same exact parent whose basenames
  differ only by canonical NFC/NFD representation retains the normal update or
  no-op result with a typed `unicode_normalization_mismatch` advisory. Planning
  preserves the target's observed spelling and never normalizes either name.
  Ambiguous groups and target entries already claimed by exact matches are not
  paired heuristically.
- Move detection requires unambiguous prior source correspondence, stable
  identity, link count one, unique identity occurrence, and a safe target-side
  move. It never equates source and target filesystem IDs.
- A rename plus content change is one composite move-update intent with one
  final ledger result, even if execution uses recoverable internal stages.
- A directory rename always decomposes into per-file identity moves, the full
  parent-first mkdir chain, and dependency-ordered cleanup of directories made
  empty by those moves. There is no M0 directory-move operation; interfaces may
  group the decomposition as one folder-level review item.
- Unsupported scan entries remain visible and blocked; they do not vanish from
  the plan.

## Capacity

One pure capacity function is shared by planner and preflight. Required bytes
cover the maximum concurrent target-volume temps plus operation-specific
overheads and never count move/trash/delete metadata operations as transferred
content. Live trash consumes space until a retention workflow actually removes
it. Reclaimable orphan temps are an observation used by preflight, not optimistic
planner state.

Stage 1 removed `worker_count` from options, plans, fingerprints, and payloads.
The current executor admits one file operation at a time, and the capacity
contract has no dormant file-concurrency tuning input.

At the active checkpoint-3.2 scalar cutover, planner construction follows the checked-
arithmetic and pre-publication refusal contract in
[M1_BRIDGE.md](M1_BRIDGE.md) and [DEFENSE.md](DEFENSE.md) §1.3; planner defines
no local numeric domain. Every logical-byte rollup uses checked signed-64
addition; an aggregate excess refuses publication with the typed plan/domain
`logical-bytes` review-limit fact rather than wrapping or becoming a free-space
diagnostic.

The function consumes target `CapabilityProfile.supports_hardlinks`, populated
from the Windows `FILE_SUPPORTS_HARD_LINKS` volume flag. For each concurrently
in-flight update on a non-hardlink target it counts both the new replacement
temp and the displaced old-version backup copy. It does not infer support from
filesystem name or an attempted operation.

## Scope And Selection

M0 implements `Scope.everything()` plus workflow-owned safe-subset selection.
Pattern, explicit, and recorded-run scopes
are declared now. Scope uses canonical stable candidate identities, not raw UI
row numbers or display paths. The implemented selector closes dependencies,
recomputes capacity/summaries, and reports forced exclusions; user-edited
partial selection remains deferred.

The accepted Stage 6 review surface is a memoized workflow/interface
projection of one immutable plan. Planner remains the authority for operations,
dependencies, reasons, immutable statistics, and the pure dependency-closed
selection calculation; search, collapse, windows, anchors, accessibility
framing, live result overlays, and inferred move-peer presentation do not alter
the plan.

Multiple operations targeting one canonical path remain distinct executable
members even when presentation groups them. Selection is global and
dependency-closed, independent of filter and viewport, and execution commits to
its exact digest. Notices are informational and cannot enter selection,
collapse, path, detail, or execution scope. A refused bounded projection stages
no partial review artifact. Exact tree frames, revisions, hard walls, paging,
rollups, overlays, and move-peer suppression rules are owned by
[M1_BRIDGE.md](M1_BRIDGE.md), with numeric containment in
[DEFENSE.md](DEFENSE.md) §1.3.

Replay, undo, and repair always plan fresh against current scans/evidence. A
historical operation list is scope input, never executable authority.

## Destination Policy And Ingest Provision

The M0 identity policy returns a batch assignment. Batch shape is permanent so
future templates can detect collisions and keep companion groups together.
Assignments must be deterministic, root-relative, collision-complete, and path
validated. Policy/enrichment versions and all assignment inputs are snapshotted
in the plan. Ingest origin evidence uses feature-owned namespaced annotations
(`ingest.origin.*`) so a later implementation does not require new generic
schema. No policy receives filesystem or executor control.

The semantic-settings `preserve_ads` policy has no dedicated CLI/UI control and
its transfer behavior remains latent. When it is implemented, planner's only
ADS responsibility is a mapping-level warning when the target capability cannot
carry streams; enumeration, byte transfer, and validation remain executor-time
work. M1 has no ADS-enabled mapping or per-operation ADS state.

## Expectations Of Other Modules

- Scanner supplies complete typed snapshots and conservative capabilities.
- Database repositories supply immutable prior correspondence; planner never
  writes it.
- Workflow snapshots policies/settings and coordinates enrichment.
- Preflight judges the plan against a later world without altering it.
- Executor follows operation/dependency intent exactly and reports outcomes; it
  never improves or repairs a plan.
- Interfaces may filter/render operations but cannot change dependency rules.

## PoC Hardening

- Full mkdir chains fix nested empty-directory non-convergence.
- Planned-removal-aware cleanup fixes orphaned target directories.
- One capacity function and explicit concurrency fix multi-update undercount
  and planner/executor formula drift.
- Mapping evidence includes paired no-ops so later renames do not degrade to
  copy+trash.
- Incomplete scans and unsupported entries remain visible; unsupported items
  are blocked, while workflow permits only completeness-independent operations.
- Managed-attribute-only drift is update-worthy; unmanaged attribute drift is
  retained as evidence without causing a non-convergent update. The remaining
  metadata no-op risk is content changing behind equal size/time/managed
  attributes, and later content evidence is additive.
