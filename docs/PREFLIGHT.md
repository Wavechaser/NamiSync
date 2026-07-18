# Preflight Module

Status: M0 observation and pure judgment implementation complete. Fresh
preflight remains mandatory immediately before every managed-data mutation,
on resume, and on queued wakeup.

## Purpose

Preflight separates current-world observation from pure judgment:

```python
observe(xset: ExecutionSet, fs: FileSystem,
        settings: SettingsReader) -> ObservedWorld
preflight(xset: ExecutionSet, world: ObservedWorld) -> Verdict
```

## Implemented M0 Surface

`namisync.modules.preflight.observe()` consumes an injected read-only
filesystem and settings reader. It records only remaining selected-operation
subjects, required target parents, both roots, capacity, exact reclaimable temp
bytes, trash safety, settings, and one UTC timestamp. The native local backend
performs no cleanup or hydration.

`preflight()` consumes only the immutable `ObservedWorld` contract in
`namisync.core.preflight`. It reports all applicable typed run- and
operation-level refusals for incomplete scans, root/volume ambiguity, broken
selection dependencies, blocked work, direct or parent-path drift, policy
drift, insufficient capacity, trash safety, containment, and target path
representation. Commitment checking remains at the execution-workflow entry,
as review preflight intentionally works before a commitment exists.

`observe()` performs read-only IO, including reading current semantic settings,
and decides nothing. `preflight()` performs no IO and changes nothing. Neither
repairs, re-plans, drops, cleans, or executes operations.

## Observation Boundary

Observation touches only remaining selected-operation paths and their required
parents/roots. It records source and target stats (or absence), root/physical
volume evidence, free space, exact reclaimable owned-temp bytes, trash path
resolution/writability, current filters from the injected settings reader, and
one injected UTC timestamp.

Stats are keyed by `Subject(root, rel_path_key)`, never by relative-path string
alone.

Every path is first lexically validated, then opened/resolved under its root
with long-path-safe, reparse-aware handling. Reclaimable temp accounting accepts
only the exact NamiSync temp grammar, in touched target parents, outside trash,
on the target volume. Observation never deletes those files.

An observation failure is evidence, not an exception that silently skips a
check. The snapshot records unknown/unavailable state so pure judgment refuses
the affected operation.

## Judgment Rules

Preflight returns all applicable typed refusals, grouped per operation and for
the run. It verifies:

- both original scans were complete modulo recorded ignores;
- roots remain distinct, non-nested, and bound to the reviewed volume evidence;
- cloned/ambiguous volumes are not guessed;
- selection is dependency-closed;
- no selected operation depends on blocked, failed, canceled, or deferred work;
- current source/target/type/identity/size/mtime evidence matches each planned
  before-state within capability granularity;
- expected absence is still absence and expected destination occupancy/type is
  unchanged;
- current semantic filter/options/policy fingerprint equals the plan snapshot;
- current required bytes for remaining operations fit free space plus safely
  reclaimable owned temps;
- trash resolves beneath the target, on the same physical volume, without a
  reparse escape, and is writable;
- every final destination remains root-constrained and representable on the
  target filesystem.

Unrelated tree changes do not matter. A refusal never mutates `ExecutionSet`,
silently removes an operation, or changes an operation to a safer-looking kind.

Commitment validation is not preflight judgment: review uses preflight before a
commitment exists. `run_execution` must refuse a missing plan fingerprint or
selection-digest match before it calls observation/preflight.

## Repetition And Freshness

Plan review may display a verdict from one observation. Execution always makes
a fresh observation; it does not reuse the review snapshot merely because it is
recent. This resolves the contradictory reuse wording noted during review: time
closeness is not evidence of unchanged state. Resume and queue wakeup likewise
observe fresh.

Residual TOCTOU remains after observation. Executor therefore performs a final
per-operation guard immediately before each mutation; preflight does not replace
those guards.

## Capacity And Temp Recovery

The pure required-byte calculation comes from core/planner. Preflight may count
owned orphan temps as recoverable only if executor will remove exactly those
artifacts before allocating new temps. If cleanup later fails or actual free
space falls below the verdict, executor fails safely without publishing partial
content. User files resembling temp names never count as recoverable.

The shared formula uses the target's reviewed
`CapabilityProfile.supports_hardlinks`; a no-hardlink update selection includes
the old target's backup-copy bytes as well as replacement temps. Preflight never
probes support or substitutes a filesystem-name guess.

## Expectations Of Other Modules

- Planner embeds every before-state and policy snapshot needed for judgment.
- Core supplies path/volume/evidence types and the shared capacity function.
- Workflow supplies the injected settings reader used by observation.
- Dispatcher holds/acquires required volume custody around execution; preflight
  verifies identity but does not own locks.
- Workflow alone invokes fresh observe/preflight immediately before executor
  mutation under the same custody. Executor imports no preflight sibling and
  retains live per-operation guards as the final TOCTOU defense.
- Interfaces show refusal reasons without offering an execute-anyway bypass.

## Latent Features

Partial execution and resume add selection/status cases, not new safety logic.
Queue wakeup calls the same functions. Network roots require a distinct weaker
observation/custody profile and remain refused until that profile exists. A
future continue-with-skips tier must produce explicit deferred/skipped outcomes
and a new reviewed summary; it cannot silently reinterpret a refusal.

## PoC Hardening

- Scoped stats fix whole-tree over-refusal and duplicate full-walk latency.
- Complete-scan refusal prevents hidden-subtree target deletion.
- Shared capacity calculation prevents drift and update undercount.
- Reclaimable exact temps fix nearly-full loop-refusal without broad cleanup.
- Volume/reparse validation prevents trash from becoming cross-volume
  copy-delete.
- Fresh execution observation closes the plan-to-execute stale-plan gap as far
  as possible; executor live guards narrow the residual window, and only
  operation-specific mutation primitives can enforce touch-time conditions.
  Non-replacing destinations and emptiness checks do not by themselves bind a
  source pathname to the object previously observed; that requires an explicit
  handle-bound operation or remains inside the external-writer boundary.

## Acceptance Criteria

- Pure-preflight tests run with no filesystem object and cover every refusal
  combination without mutation.
- Read-only harness proves observation creates, deletes, renames, hydrates, or
  writes nothing.
- Instrumentation proves observation stats only selected touched paths and
  required parents/roots; an unrelated change never refuses the plan.
- Every incomplete-scan plan is refused, including a plan with no apparent
  target-only operations.
- Source drift, target drift, type change, identity change, destination
  appearance, root swap, volume clone ambiguity, filter drift, and dependency
  break each yield typed refusals.
- Same-volume, contained, writable trash passes; reparse, off-volume, readonly,
  and unresolved trash fails before mutation.
- Capacity boundary/property tests agree with planner for full and partial
  selections, include no-hardlink backup copies, and safely count only exact
  reclaimable temps outside `.synctrash`.
- Review, immediate execution, resume, and queue wakeup return identical
  verdicts for identical snapshots and fresh different verdicts after drift.
- Refusal leaves plan, selection, statuses, filesystem, and ledger byte-for-byte
  unchanged.
- Missing or mismatched plan/selection commitment is refused by execution entry
  before observation; ordinary review preflight remains usable without one.
- A test changes an unrelated file between plan and execution and still passes;
  a touched file change refuses.
- Long-path and root-escape cases are judged through canonical validated paths.
- Import-linter proves preflight imports core but no sibling module.

## M0 Verification

`tests/test_preflight.py` contains 29 focused tests. Pure-verdict fixtures run
without a filesystem, while instrumented observation tests prove scoped reads,
fresh-world behavior, exact temp accounting, and no managed-data mutation.
