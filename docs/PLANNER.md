# Planner Module

Status: M0 path-preserving paired-sync implementation complete. Later scopes,
content evidence, ingest policies, replay, repair, and undo reuse the same plan
shape.

## Purpose

The planner is a pure deterministic transformation from immutable evidence and
policy snapshots to an immutable `Plan`. It decides intended operations and
dependencies; it never touches the filesystem, writes a database, asks a human,
or executes/repairs anything.

## Required Inputs

```python
plan(source: ScanResult, target: ScanResult,
     correspondence: MappingSnapshot, options: SyncOptions,
     scope: Scope) -> Plan
```

## Implemented M0 Surface

`namisync.modules.planner.plan()` is a pure transformation over frozen core
snapshots. `namisync.core.planning` owns the serializable plan, operation,
assignment, policy, scope, deterministic-id/fingerprint, selection-digest,
and shared capacity contracts. M0 implements `Scope.everything()` and the
batch-shaped identity destination policy; the other scope constructors remain
declared but raise rather than pretending to work.

The implementation emits explicit parent-first directory operations, file
copy/update/no-op intent, correspondence-qualified move or composite
move-update intent, target-only policy operations, and dependency-ordered
directory cleanup. Blocked unsupported/collision items remain in the plan.
Planner and preflight both call `calculate_required_bytes()`; neither stores or
guesses target free space.

`options` contains deletion and preservation policies, the symmetric mapping
filter snapshot, the selected `DestinationPolicy`, and the latent
`propagate_source_casing` policy plus any already-extracted enrichment metadata.
The casing policy defaults to false and is not exposed by a config file, CLI, or
GUI yet. `MappingSnapshot` contains prior accepted pairs/no-ops, retained missing
rows, and ambiguity/hardlink disqualifiers keyed by canonical path. Observed
target free space is deliberately absent: review and execution call `observe()`
and judge the same pure required-byte formula against current space.

No input may be fetched from SQLite, settings, clock, or filesystem inside the
planner.

## Plan Contract

A plan snapshots roots and `VolumeId` evidence, complete-scan state, filters,
semantic options, `PreservationPolicy`, policy/version fingerprint,
deterministic operations, dependency graph/order, required volumes, required
content bytes, concurrency assumption, and all source/target stat evidence
needed by preflight. It contains no target-free-space observation.

Each operation has a stable id derived from canonical intent—not list position
or random state—and includes kind, source/target relative paths, expected
before-state, intended after-state, byte contribution, reason code,
dependencies, and blocked/conflict detail. Execution never recomputes target
paths or destination policy. Expected/intended metadata uses
`MetadataSnapshot` (attributes and creation time) under the snapshotted
preservation policy. No stream manifest enters a plan.

Canonical JSON remains byte-compatible for valid Unicode paths and escapes a
malformed surrogate code unit defensively instead of raising during operation-id
or plan-fingerprint construction. The scanner rejects such code units before a
path record exists; serializer hardening prevents unrelated free-form data from
turning a review into a raw encoding failure.

`ExecutionSet` selects a dependency-closed subset and carries per-operation
status. Its optional `Commitment` binds both the plan fingerprint and a
deterministic digest of that exact selection; changing either invalidates the
commitment. Workflow derives M0's safe subset from the full plan: direct
blockers stay `BLOCKED`, correspondence/dependency exclusions stay `DEFERRED`,
and incomplete scans withhold destructive/identity operations. Planner itself
continues to emit complete deterministic intent and does not hide those items.

## Diffing And Operation Rules

- Compare through `DestinationPolicy.assign()`, including the M0 identity
  assignment; never directly assume source path equals target path.
- Apply mapping filters symmetrically before diffing. Location ignores have
  already bounded scan completeness.
- Compare mtimes within the coarser capability granularity.
- Matching size, mtime within the coarser granularity, and standard attributes
  is an M0 metadata no-op. An attributes-only change plans an update even when
  size and mtime are unchanged. Content-aware no-op comes later.
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
  target's observed spelling. The latent `propagate_source_casing=True` policy
  instead forces an update at the source basename spelling; the native atomic
  replacement recases that directory entry on ordinary case-insensitive NTFS.
  It does not recase parent directories, and case-sensitive targets can refuse
  the exact-path preflight rather than being guessed through.
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

The plan snapshots the worker-count/concurrency assumption used by the formula;
executor may use fewer workers but never more without re-planning/re-preflight.

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

The unexposed `preserve_ads` policy is latent. When it is implemented, planner's
only ADS responsibility is a mapping-level warning when the target capability
cannot carry streams; enumeration, byte transfer, and validation remain
executor-time work. M0 has no ADS-enabled mapping or per-operation ADS state.

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
- Attribute-only drift is update-worthy; the remaining metadata no-op risk is
  content changing behind equal size/time/attributes, and later content
  evidence is additive.

## Acceptance Criteria

- Repeated serialization of identical inputs is byte-identical, including ids,
  ordering, reasons, summaries, and assignment.
- Randomized input ordering produces the same plan.
- Nested empty directory fixtures create every level parent-first and an
  immediate rescan/replan converges to no mutations.
- Non-empty parent chains also produce explicit metadata-bearing mkdirs, and
  every file/child operation depends on its nearest created parent.
- Renamed-directory fixtures decompose into per-file moves, mkdir dependencies,
  and safe emptied-directory cleanup; UI grouping does not change executable
  operation ids or dependency order.
- Target directories emptied by same-plan operations receive safe dependent
  cleanup; nonempty/unselected directories never do.
- Additive emits no target-only mutation; trash is default; mirror is rejected
  unless internal authorization is explicit.
- Every operation path passes core validation, remains under its root, and
  supports long destination paths.
- Stable-identity-less, duplicated-identity, multi-link, ambiguous prior
  correspondence, and cross-location cases emit no move.
- Persisted paired-noop evidence enables an unambiguous later rename to plan a
  target-side move.
- Move-update has one operation id and no intermediate state that can be
  recorded as final success.
- Same-side case collisions and file/directory collisions are blocked and
  visible; one-to-one case and NFC/NFD spelling mismatches are non-blocking
  typed advisories whose underlying update/no-op work remains executable.
- Default planning preserves target spelling. Opt-in source-basename casing is
  fingerprinted, survives workflow-payload round trips, and forces an atomic
  replacement only when the basename casing differs.
- Incomplete source or target scans yield a reviewable full plan whose workflow
  selection admits copy/update/mkdir/noop and withholds move/move-update/trash/
  delete; preflight refuses any caller that reintroduces withheld operations.
- Capacity property tests never undercount any allowed worker schedule and use
  the exact same function as preflight.
- No-hardlink update fixtures include displaced-version backup bytes under every
  allowed worker schedule; hardlink-capable fixtures do not charge content bytes
  for the link itself.
- Filter application is symmetric; excluded retained rows are not planned as
  missing/deleted, and the filter snapshot is serialized.
- A readonly/hidden/system-only difference with unchanged size and mtime plans
  an update and propagates through the real sync workflow.
- Destination policy collision and companion-group property tests produce
  deterministic, unique, reviewable assignments.
- Planner tests use no filesystem/database fixture, proving purity.
- Import-linter proves planner imports core but no sibling module.

## M0 Verification

`tests/test_planner.py` contains 30 filesystem-free planner tests covering
random input order, byte-identical serialization, directory convergence,
cleanup dependencies, move disqualifiers, policy collisions, symmetric
filters, case/NFC advisory behavior, long paths, and hardlink-aware capacity.
Payload and native replacement coverage proves the latent recasing seam; a
reviewed-sync regression proves changed content is not suppressed by a casing
advisory and default target spelling is retained.
Shared path/serialization contracts are covered in
`tests/test_core_scanplan.py`.
