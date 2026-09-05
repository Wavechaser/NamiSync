# Preflight Module

Status: M0 observation and pure judgment implementation complete, with M1
Stage 1's immutable reviewed-policy semantics and shared ephemeral root
authority. Fresh preflight remains mandatory immediately before every
managed-data mutation, on resume, and on queued wakeup. Stage 6's pre-model
plan-review source/refusal admission is active for workflow-supplied review.

Preflight uses the active capacity-observation and refusal contract in
[BRIDGE.md](BRIDGE.md) and
[DEFENSE.md](DEFENSE.md) §1.3 without defining a local numeric variant.

## Purpose

Preflight separates current-world observation from pure judgment:

```python
observe(review: ExecutionReview, fs: FileSystem, *,
        review_admission: PlanReviewProducerAdmission | None = None) -> ObservedWorld
preflight(review: ExecutionReview, world: ObservedWorld, *,
          review_admission: PlanReviewProducerAdmission | None = None) -> Verdict
```

Plan-review producers and result-adoption gates accept only the exact counter-
free producer capability. They cannot charge retained rows or bytes. Separate
retained-world and retained-verdict helpers accept only the cumulative
`PlanReviewAdmission`; execution-time observer and judgment callbacks continue
without review-capacity authority, while their returned compounds receive
standalone producer admission and ordinary pre-run failure classification.

## Implemented M0 Surface

`namisync.modules.preflight.observe()` consumes an injected read-only
filesystem. It records only remaining selected-operation subjects, required
target parents, both roots, capacity, exact reclaimable temp bytes, trash
safety, and one UTC timestamp. The native local backend performs no cleanup or
hydration.

`preflight()` consumes only the frozen outer `ObservedWorld` contract in
`namisync.core.preflight`. It reports all applicable typed run- and
operation-level refusals for unsafe operations selected from incomplete scans,
root/volume ambiguity, broken selection dependencies, blocked/quarantined work,
direct or parent-path drift, insufficient capacity, trash safety,
containment, and target path representation. Commitment checking remains at the
execution-workflow entry, as review preflight intentionally works before a
commitment exists.

The six exact preflight observation and verdict dataclasses are frozen and
slotted, so instances carry only their declared fields. `ObservedWorld` copies
its three mapping inputs into private dict-backed read-only mapping proxies
after validating capacity scalars and UTC time; an exact `datetime` already
using `timezone.utc` is retained, while a datetime subclass or zero-offset UTC
alias is canonicalized before those mapping copies. Target-parent paths remain
an exact `frozenset`. Frozen observation leaves make the complete published
world deeply read-only, and later caller changes to input dictionaries cannot
change it. Fallible internal result boundaries still require exact types and
declared compound relations.

`observe()` performs read-only filesystem/volume IO and decides nothing.
`preflight()` performs no IO and changes nothing. Neither repairs, re-plans,
drops, cleans, or executes operations. Admitted execution uses the immutable
reviewed policy snapshot already bound into the plan; it never reinterprets the
run from newer global defaults.

During each preflight cycle, workflow creates one exact immutable
`ExecutionReview` and passes that same instance to observation and judgment.
Plan review supplies empty status; execution and resume copy current status only
after capturing the existing mutable execution authority. Observation gates its
selected subjects, target parents, roots, paths, stats, and backend-returned
mappings independently before first excess. The preflight module admits the
observer's exact `ObservedWorld` without rebuilding it, rejects out-of-plan
subjects, paths, parents, roots, or mismatched stat/path keys, and workflow
passes that same world identity directly to judgment. Verdict admission requires
the exact admitted world identity, gates the complete informational population
before refusal traversal, validates truth, code, selection, subject, and text
relations in place, and retains the exact callback verdict and refusal order.
An equal replacement world is not the admitted world and fails ordinarily.

Only the final observed-world mapping slots and verdict refusal-tuple slots/
informational rows are charged to the retained plan artifact. Construction
maps, keys, sorting, selection, and scope-derivation temporaries are disposable
and uncharged. A first excess is the shared typed `REFUSED+UNRUN` result and
never becomes an incomplete ordinary verdict or saved partial plan.

These source and retained-reference checks do not freeze the unrealized
complete-object constants or account for construction/container capacity,
complete projections, later task/serialization, native, or browser copies.

## Observation Boundary

Observation touches only remaining selected-operation paths and their required
parents/roots. It records source and target stats (or absence), root/physical
volume evidence, free space, exact reclaimable owned-temp bytes, trash path
resolution/writability, and one injected UTC timestamp.

Stats are keyed by `Subject(root, rel_path_key)`, never by relative-path string
alone, but observation still passes planned relative-path spelling to the
filesystem. A `recase` operation deliberately gives its old and requested names
the same subject key and validates the reviewed old-target evidence. The
executor's non-replacing rename is the final occupancy guard: an ordinary
case-insensitive target aliases the same object, while a distinct case-sensitive
destination cannot be overwritten. Preflight never normalizes NFC/NFD spelling.

Every root-dependent backend call derives an ephemeral `RootAuthority` from the
plan's logical root, optional reviewed volume anchor, and expected `VolumeId`.
Root, subject, free-space, reclaimable-temp, and trash calls each freshly admit
that authority; no earlier success is cached as permission. Admission no-follow
checks every configured-root component below the reviewed/current mount before
physical resolution, and typed anchor or volume changes remain observation
evidence for pure judgment to map to `root_changed`.

Every existing relative component of a subject, temp parent, or `.synctrash`
path is likewise no-follow admitted before physical resolution, volume probing,
writability checks, or enumeration. A missing subject remains ordinary absence;
a missing or unsafe temp parent contributes no reclaimable bytes; and unsafe
trash is unavailable. Reclaimable temp accounting accepts
only regular files with the exact NamiSync temp grammar and a run id different
from the current execution, in touched target parents outside trash on the
target volume. `ObservedWorld` retains that identical parent set for the
post-verdict recovery sweep. Observation never deletes those files.

`Root`, `Subject`, and `ObservedWorld` paths retain ordinary absolute drive or
UNC spelling. `LocalObservationFileSystem` converts roots, subjects, trash, and
temp-parent paths to extended-length spelling only at Windows I/O calls, then
converts resolved evidence back before containment checks or return. The
capability profile's `max_path` remains a separate reviewed limit; native access
does not silently override it.

An observation failure is evidence, not an exception that silently skips a
check. The snapshot records unknown/unavailable state so pure judgment refuses
the affected operation.

## Judgment Rules

Preflight returns all applicable typed refusals, grouped per operation and for
the run. It verifies:

- move, move-update, trash, and delete are selected only when both original
  scans were complete modulo recorded ignores; guarded copy, update, mkdir,
  noop, and non-replacing recase do not rely on proving tree-wide absence and
  remain admissible;
- roots remain distinct, non-nested, and bound to the reviewed volume evidence;
- cloned/ambiguous volumes are not guessed;
- selection is dependency-closed;
- no selected operation is blocked, overlaps a blocked correspondence region,
  or depends on blocked, failed, canceled, or deferred work;
- current source/target/type/identity/size/mtime evidence matches each planned
  before-state within capability granularity;
- expected absence is still absence and expected destination occupancy/type is
  unchanged;
- current required bytes for remaining operations fit free space plus safely
  reclaimable owned temps;
- trash resolves beneath the target, on the same physical volume, without a
  reparse escape, and is writable;
- every final destination remains root-constrained and representable on the
  target filesystem.

Unrelated tree changes do not matter. Observation and judgment receive no
mutable `ExecutionSet`; a refusal never changes its immutable `ExecutionReview`,
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

The pure required-byte calculation comes from core/planner. Preflight counts
owned orphan temps as recoverable only when the post-verdict sweep will attempt
to remove them once, from the same retained parent scope, before allocating new
temps. If cleanup fails or actual free space falls below the verdict, execution
fails safely without publishing partial content. Current-run temps and user
files resembling temp names never count as sweep-reclaimable.

The shared formula uses the target's reviewed
`CapabilityProfile.supports_hardlinks`; a no-hardlink update selection includes
the old target's backup-copy bytes as well as replacement temps. Preflight never
probes support or substitutes a filesystem-name guess.

Free-space and reclaimable-byte observations must each enter the nonnegative
signed-64 domain, and their effective-capacity sum uses checked addition before
comparison with the already bounded required bytes. A scalar-domain violation
fails closed; it is not relabeled as ordinary insufficient capacity.

## Expectations Of Other Modules

- Planner embeds every before-state and policy snapshot needed for judgment.
- Core supplies path/volume/evidence types and the shared capacity function.
- Dispatcher holds/acquires required volume custody around execution; preflight
  verifies identity but does not own locks.
- Workflow alone invokes fresh observe/preflight immediately before executor
  mutation under the same custody. Executor imports no preflight sibling and
  retains live per-operation guards as the final TOCTOU defense.
- Interfaces show refusal reasons without offering an execute-anyway bypass.

## Latent Features

M0 implements the first validated continue-with-skips tier in workflow:
blocked operations are explicit `BLOCKED` outcomes, quarantined/dependency work
and incomplete-scan destructive work are explicit `DEFERRED` outcomes, and the
review summary/digest describes the resulting selection. Preflight does not
perform those exclusions; it independently refuses a caller that reintroduces
them. User-edited partial selection and resume policy remain later selection/
status cases, not new safety logic. Queue wakeup calls the same functions.
Network roots require a distinct weaker observation/custody profile and remain
refused until that profile exists.

Native subject observation currently repeats root and volume evidence reads for
present selected subjects. This is conservative and can be expensive on very
large plans, but it is not a correctness failure. Any optimization must cache
only inside one `observe()` invocation, retain a final root/full-volume
revalidation, and prove reduced native call counts under a large-plan benchmark;
a process-lifetime volume cache would make remount evidence stale and is not an
acceptable shortcut.

## PoC Hardening

- Scoped stats fix whole-tree over-refusal and duplicate full-walk latency.
- Operation-class completeness gating prevents hidden-subtree target deletion
  without refusing evidence-positive additive work elsewhere.
- Shared capacity calculation prevents drift and update undercount.
- Reclaimable exact temps fix nearly-full loop-refusal without broad cleanup.
- Volume/reparse validation prevents trash from becoming cross-volume
  copy-delete.
- Fresh execution observation closes the plan-to-execute stale-plan gap as far
  as possible; executor live guards narrow the residual window, and only
  operation-specific mutation primitives can enforce touch-time conditions.
  Non-replacing destinations and emptiness checks do not by themselves bind a
  source pathname to the object previously observed; that requires an explicit
  handle-bound operation or remains inside the external-writer residual classes
  and quiescent-root precondition owned by `DEFENSE.md`.
