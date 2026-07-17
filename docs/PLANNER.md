# Planner Module

Status: draft contract. Priority: M0 path-preserving paired sync; later scopes,
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

`options` contains deletion and preservation policies, the symmetric mapping
filter snapshot, and the selected `DestinationPolicy` plus any already-extracted
enrichment metadata. `MappingSnapshot` contains prior accepted pairs/no-ops,
retained missing rows, and ambiguity/hardlink disqualifiers keyed by canonical
path. Observed target free space is deliberately absent: review and execution
call `observe()` and judge the same pure required-byte formula against current
space.

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
`MetadataSnapshot` (attributes, creation time, and ADS presence) under the
snapshotted preservation policy.

`ExecutionSet` selects a dependency-closed subset and carries per-operation
status. Its optional `Commitment` binds both the plan fingerprint and a
deterministic digest of that exact selection; changing either invalidates the
commitment. Deferred operations remain explicit; omission is not a status.

## Diffing And Operation Rules

- Compare through `DestinationPolicy.assign()`, including the M0 identity
  assignment; never directly assume source path equals target path.
- Apply mapping filters symmetrically before diffing. Location ignores have
  already bounded scan completeness.
- Compare mtimes within the coarser capability granularity.
- Matching size+mtime is an M0 metadata no-op, with the documented limitation
  that content-aware no-op comes later.
- Source-only files plan copy; changed matched files plan update.
- Source-only directories plan the complete parent-first mkdir chain.
- Target-only files/directories follow additive/trash/internal-mirror policy.
- Directory cleanup reasons about removals planned in this same plan, not only
  the pre-scan tree.
- Case and file/directory collisions become blocked operations with no guessed
  winner.
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

The non-hardlink trash-on-update fallback is not implementation-ready in the
authoritative type set: `CapabilityProfile` does not expose hardlink support and
the capacity text does not say that the old-target backup copy consumes space
in addition to the replacement temp. Non-hardlink updates must remain refused
until the capability and formula are made explicit; otherwise preflight can
approve a predictably ENOSPC update.

## Scope And Selection

M0 implements `Scope.everything()`. Pattern, explicit, and recorded-run scopes
are declared now. Scope uses canonical stable candidate identities, not raw UI
row numbers or display paths. Partial selection closes dependencies, recomputes
capacity and summaries, and marks valid omitted work `DEFERRED` once partial
execution exists.

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
- Incomplete scans and unsupported entries remain visible and non-executable.
- Metadata no-op risk is explicit and later content evidence is additive.

## Acceptance Criteria

- Repeated serialization of identical inputs is byte-identical, including ids,
  ordering, reasons, summaries, and assignment.
- Randomized input ordering produces the same plan.
- Nested empty directory fixtures create every level parent-first and an
  immediate rescan/replan converges to no mutations.
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
- Case and file/directory collisions are blocked and visible; independent work
  remains executable after dependency closure.
- Incomplete source or target scans yield a reviewable plan that preflight must
  refuse.
- Capacity property tests never undercount any allowed worker schedule and use
  the exact same function as preflight.
- Non-hardlink update fixtures are refused until their backup-copy bytes and
  capability are represented; after that contract is added, those bytes are
  included in the same capacity property tests.
- Filter application is symmetric; excluded retained rows are not planned as
  missing/deleted, and the filter snapshot is serialized.
- Destination policy collision and companion-group property tests produce
  deterministic, unique, reviewable assignments.
- Planner tests use no filesystem/database fixture, proving purity.
- Import-linter proves planner imports core but no sibling module.
