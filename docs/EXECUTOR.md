# Executor Module

Status: M0 implemented. The native single-worker executor covers every reviewed
operation kind on local Windows filesystems, with focused acceptance coverage.
External writers remain outside NamiSync's volume-lock contract; the residual
update race is documented below rather than presented as closed.

## Purpose

The executor is the only module that applies a reviewed `ExecutionSet` to
managed user data. It implements plan operations exactly, enforces final guards,
publishes content atomically where the platform permits, emits progress/item
events, and records successful evidence through `Recorder` only after the
filesystem result exists.

It does not scan, plan, choose conflict resolutions, infer new destinations,
write SQL, own volume locks, prompt a human, or treat a policy callback as an
alternate execution engine.

## Entry Contract

```python
execute(xset, ctx, recorder, policies, fs) -> OperationResult
```

The caller holds deterministic physical-volume custody and validates that the
`Commitment` matches both immutable plan fingerprint and exact selection digest
before preflight. Workflow alone performs a fresh observe → preflight → execute
sequence on every start/resume; executor imports no preflight sibling. A refusal
permits no temp cleanup or other mutation. After a successful verdict, workflow
passes preflight's touched-target-parent scope to the executor filesystem for
one exact prior-run temp sweep, then processes dependency-ready operations in
plan order. A sweep failure stops before any planned operation is admitted.

The core generic session runner emits the single terminal event. Executor emits
phase, progress, and item outcomes only, returns one complete result,
and lets `Canceled`/`PauseRequested` unwind to that runner after its own safe
operation-boundary cleanup.

## Universal Operation Rules

- Checkpoint before each operation and at operation-specific safe boundaries.
- At each operation's point of touch, revalidate its direct source/target
  preconditions against live filesystem evidence: expected identity/type/stat,
  required absence/occupancy, root containment, and directory emptiness where
  relevant. Drift fails that operation without guessing.
- Validate paths lexically and by resolved handle; use long-path-safe APIs.
- Use operation-matched conditional primitives where Windows provides them:
  `CREATE_NEW` for temps, non-replacing rename when destination absence is a
  precondition, and `RemoveDirectory` for atomic nonempty refusal. Never follow
  a reparse escape.
- Flush recorder before a destructive operation when required by the durability
  window.
- Record one final typed outcome per selected operation; dependencies of a
  failed operation become explicit canceled/deferred outcomes, while independent
  operations continue. Pause leaves completed status intact and unreached work
  pending in `ExecutionSet`.
- Byte progress counts copied/updated content only.
- Policies return `Continue`, `Stop`, or bounded `Retry(after)` decisions; the
  executor retains guards, limits, checkpointing, and final outcome ownership.

An immediate stat followed by a path-based mutation is detection, not an atomic
condition: an unrelated process can replace the path between those calls even
though NamiSync's own volume lock is held. Conditional primitives close the
occupancy/emptiness cases named above. Update's backup-then-replace sequence
retains one external path-swap window between its final guard and replacing the
live name. External processes mutating a managed target root during execution
are outside the safety contract; this residual must remain visible in tests and
documentation rather than becoming a false compare-and-swap guarantee.

## Copy State Machine

1. Validate expected source and destination states.
2. Create an exclusive exact-name temp in the final target parent and volume.
3. Stream source bytes through `CopyBackend` in bounded chunks while hashing and
   checkpointing; backend writes bytes only.
4. Copy the current source security descriptor only when ACL preservation is
   opted in; failure fails the operation. ADS is not part of the M0 state
   machine.
5. Flush content to the medium, apply creation time/standard attributes under
   the plan's `PreservationPolicy` except readonly, and flush again when metadata
   durability requires it. Readonly is applied only after publish.
6. Re-stat source. Drift fails and removes/quarantines the temp; no attestation
   is recorded.
7. Re-check destination expected absence/state at publish and use a conditional
   atomic primitive appropriate to the planned before-state.
8. Atomically publish with the Windows/local-filesystem primitive.
9. Open the parent directory with `GENERIC_WRITE` and
   `FILE_FLAG_BACKUP_SEMANTICS`, then attempt a best-effort flush. A refused or
   unsupported flush is a per-operation durability warning; the result claims
   durability only for what was actually flushed.
10. Stat the published target and construct `Attestation(ContentEvidence,
   target_stat)` so target identity is never confused with source identity.
11. Call recorder. A recorder failure preserves the filesystem outcome and
    degrades `RecordingStatus` instead of relabeling the copy as failed.

Temps use `<name>.synctmp-<run-id>-<op-id>` with validated fixed-format ids.
Once per successfully preflighted execution, recovery enumerates only direct
children of the same touched target parents used for capacity accounting. It
removes exact-grammar regular files whose embedded run id differs from the
current run; current-run temps remain under per-operation retry/cancel cleanup.
Recovery never recurses, enters `.synctrash`, or deletes a substring lookalike.

## Update And Trash-On-Update

An update completely prepares and validates the replacement temp before it
touches the current target. With trash-on-update enabled it then:

1. validates/reserves `.synctrash/<run-id>/<relative-path>` on the target volume;
2. preserves the old live file there using a same-volume hardlink when
   `CapabilityProfile.supports_hardlinks`; otherwise writes a trash-local exact
   temp, flushes it, and atomically publishes the complete backup inside the run
   directory before proceeding;
3. clears readonly on the live target if Windows requires it for replacement;
4. atomically publishes the prepared temp over the live path with `os.replace`;
5. applies the new file's readonly bit and remaining post-publish metadata;
6. performs the best-effort parent flush, re-stats, and records success.

No crash point leaves the live path absent. A crash after hardlink creation but
before replacement leaves the old live inode with link count two; that is a
benign, scan-visible hardlink warning which disables move detection until the
trash link is purged. Rerun reconciliation distinguishes exact owned temp/run
backup/already-published state from unrelated user files and converges without
discarding the only known-good version.

The planner/preflight formula includes backup-copy bytes on no-hardlink targets.
A partial backup remains under exact temp grammar, is ignored by restore
planning, and ages out with the trash run directory; ordinary temp recovery
still never walks `.synctrash`. Readonly ordering/recovery restores the old
version's planned attributes after replacement so the hardlinked trash inode is
not left silently degraded.

The final guard cannot make the subsequent path-based replacement conditional
on target identity. If an external process swaps the live target after backup
and guard but before replacement, that external file can be replaced without
being the version preserved in trash. NamiSync still records only the
post-publish target it actually created, so the ledger is not falsely attached
to the displaced object. The inter-call interval is normally very short but is
not scheduler-bounded; tests assert the bounded data consequence, not a timing
claim.

## Other Operations

### Move

Revalidate old target and new destination, refuse occupancy, perform a
same-volume non-replacing atomic rename whose primitive itself fails if the
destination appeared, attempt best-effort parent-directory flushes, stat the
result, then record correspondence. Source identity must be validated on the
object being renamed where the OS API permits handle-relative rename. A vanished
or swapped old target yields a typed skipped/failed outcome and must not leave
the old ledger row `present`.

### Composite move-update

Publish the changed content at the new path first, then trash the old path. One
plan operation may have internal prepare/publish/trash stages, but only one
final outcome and ledger transition. A crash after any internal stage may leave
both old and new versions, never neither, and leaves no completed mapping claim.

### Mkdir

Create only the planned directory after validating parent containment and
expected absence. Existing matching directories may converge to a typed no-op;
the create primitive must atomically fail if a new entry appeared, and
wrong-type entries fail. Apply source directory attributes and restore directory
timestamps only after all descendant child operations have settled.
Every created directory has its own reviewed mkdir-with-metadata operation from
an all-directory `DirRecord`; executor never creates implicit parent paths.

### Trash

Resolve trash under the target on the same physical volume, create guarded run
parents, refuse reparse/off-volume paths, use a non-replacing rename that fails
atomically on trash collision, and validate the source object at touch. Never
degrade to copy-delete. Record only after the rename succeeds.

### Delete and directory cleanup

Mirror deletion remains internal/guarded. Re-stat type and identity immediately
before deletion and use the strongest available handle-conditional delete.
Only a dependency-complete `directory_cleanup` delete may ignore mtime and link
count churn caused by removing its own planned children; it still requires exact
kind, size, attributes, and creation time. A stable identity binds exactly when
the reviewed scan supplied one; absent identity is absent evidence, not a veto.
Directories must be empty at deletion time and `RemoveDirectory` enforces that
condition atomically. Never recursively delete an unplanned subtree.

### No-op

Perform no user-data mutation. Any correspondence/last-seen recording is
conditional on both sides still matching the plan snapshot, including identity;
otherwise record a stale/skipped outcome rather than refreshing false evidence.

## Cancellation, Pause, And Failure

Copy chunks are bounded so cancel/pause latency is bounded. Either request
unwinds rather than blocking. Executor catches `Canceled` only long enough to
clean/retain exact owned temps and emit reliable canceled outcomes for the
in-flight and unreached selection, then re-raises for runner aggregation and the
one canceled terminal. Pause abandons/reclaims an in-flight temp through
ordinary exact-name recovery, preserves completed `ExecutionSet` statuses,
forces pause-drain recording, and re-raises without terminal; dispatcher then
releases custody. Resume queues at the back, freshly re-observes/preflights in
workflow, and continues only unreached work.

Sharing violations use bounded retry with injected clock/backoff and checkpoint
between attempts. A simple operation restarts after exact-temp cleanup; an
update or move-update with a durable sub-step retains an operation-local
continuation, revalidates the prepared/published file and owned backup/trash,
and resumes at replace or old-to-trash rename instead of colliding with its own
hardlink or published destination. It also recognizes the exact committed state
if an injected/native boundary reports failure after the syscall took effect.
Persistent failure records `sharing-violation` after the configured bound and
independent work continues. Unexpected executor exceptions are contained by the
session wrapper, release custody, and never suppress already-earned outcomes.

## Progress

`Progress` snapshots carry content bytes done/total, items done/total, and the
current path; `PhaseChanged` carries the phase separately. Moves, trash, mkdir,
delete, and no-op contribute items but zero transfer bytes. Failed work is not
credited as completed content. Emission is throttled/coalesced outside the copy
chunk size so fast disks cannot flood UI queues.

## Expectations Of Other Modules

- Core supplies operation/evidence/result types, path guards, checkpoint, and
  policy protocols.
- Planner supplies complete immutable intent and expected before/after states;
  executor never recomputes them.
- Preflight supplies fresh verdict semantics, while executor retains final
  per-operation guards.
- Dispatcher/session runner owns physical-volume custody, pause/cancel control,
  and terminal ownership.
- Workflow aggregates execution, recording, and optional verification results.
- Filesystem mutation succeeds before its record call.
- Destructive boundaries force prior recorder state durable.
- Copy digest provenance never sets `last_verified_at`.
- Recorder calls are idempotent under run/op tokens and conditional evidence.
- Recording failures are never swallowed or mislabeled as byte-copy failures.
- History observes events independently; executor never writes history.

## Latent Features

- Partial execution uses the existing selection/dependency/capacity model and
  explicit `DEFERRED`; it cannot skip closure checks.
- Multiple workers are enabled only by `WorkerCountPolicy`, plan-snapshotted
  capacity, deterministic outcome aggregation, and per-volume characteristics.
- Restartable copy requires a versioned partial-file/digest checkpoint whose
  ownership and source snapshot are validated before reuse.
- ADS preservation, when exposed later, enumerates and validates source streams
  during copy without adding scanner, plan-operation, or database manifests.
  Requested stream loss on a capable target fails the operation; stream bytes
  remain outside capacity/progress totals and main-stream attestations.
- Throttling wraps chunk pacing without changing event semantics.
- Robocopy may supply bytes through `CopyBackend`; it never owns planning,
  trash, publish, final guards, or ledger claims.

## PoC Hardening

This contract directly covers the PoC first-failure abort, stale-plan TOCTOU,
large-copy cancellation, missing move handling, empty-directory omission,
whole-tree preflight, broad temp deletion, false byte totals, unsafe
incomplete-scan destructive execution, cross-volume trash, orphan-temp capacity loop, missing source-drift
attestation guard, and composite move-update gap.

## M0 Implementation

`namisync/core/execution.py` owns `ExecutionSet`, validated run identifiers,
typed executor reasons and decisions, and the filesystem/copy/recorder
protocols. `namisync/modules/executor.py` supplies `NativeFileSystem`,
`NativeCopyBackend`, `BoundedFailurePolicy`, `ExecutorPolicies`, and `execute`.
The implementation has no sibling-module import; workflow supplies the reviewed
and freshly preflighted set, dispatcher/session owns custody and terminal
aggregation, and the run-bound recorder owns durable ledger interpretation.

The focused M0 suite exercises all eight operation kinds; atomic conditional
publish and displacement; hardlink and copy-backup update paths; source and
target drift; ACL and readonly ordering; prior-run exact temp recovery and
current-run/lookalike isolation; reparse/off-volume
trash refusal; move/composite failure bounds; dependency continuation; deferred
directory metadata; cancel, pause, unexpected interruption, simple and
multi-step bounded sharing retry, recorder degradation, progress throttling,
and copy attestations. The
workflow/dispatcher/recorder suites cover the acceptance responsibilities that
belong outside this module, including fresh preflight, custody, one terminal,
and durable run-token idempotency.

## Acceptance Criteria

- Fault injection before/after every state-machine step proves no partial file
  is published, no success is recorded early, and every owned artifact is
  recoverable without touching user lookalikes.
- Copy/update publish is same-volume atomic; target bytes are either the complete
  prior version or complete new version, and the displaced version exists in
  exact run trash before replacement publishes.
- Fault injection between hardlink/copy-backup, readonly clearing, replace,
  metadata, flush, and record leaves a recoverable state; an interrupted
  hardlink backup is a documented `nlink>1` warning and rerun converges.
- On a no-hardlink target, backup fault injection leaves only an exact temp or a
  complete published trash version; restore ignores the former and capacity
  includes its content bytes.
- Source mutation during any chunk or before final stat fails the operation and
  records no digest/attestation.
- Opt-in ACL copy failure fails before publish and leaves the prior live target
  untouched. ADS has no M0 acceptance case because the policy is not exposed.
- Target appearance/change after preflight but before mutation is detected by
  the final guard when it occurs before that guard. Faults injected between
  guard and touch prove only the condition owned by the mutation primitive:
  non-replacing rename rejects destination appearance and `RemoveDirectory`
  rejects nonempty directories. Source-object swaps are rejected only by an
  explicitly handle-bound mutation; otherwise they remain inside the disclosed
  external-writer boundary. Update fault injection proves an external swap may
  replace the swapped file without trashing it but cannot create a false ledger
  attestation or publish partial bytes.
- First blocked/failed work does not abort later independent operations; broken
  dependents receive explicit outcomes.
- Exact temp recovery removes prior-run regular files only from preflight's
  touched-parent scope; current-run temps, substring lookalikes, exact-name
  directories, untouched parents, off-volume mounts, and `.synctrash` survive.
  Cleanup failure stops before copy allocation or publication after preflight
  credited those bytes.
- Trash cannot escape through reparse points, cross volumes, overwrite a trash
  collision, or degrade to copy-delete.
- Move occupancy, vanished-old-path, wrong type, and retained-missing-row cases
  produce correct filesystem and recorder outcomes without rolling back other
  earned records.
- Directory create/delete tests cover full chains, wrong types, nonempty races,
  no recursive unplanned deletion, and metadata application only after every
  child operation has settled; every created empty or non-empty directory comes
  from its own reviewed `DirRecord` operation.
- Same-run trash/move cleanup tolerates only directory mtime/link-count churn,
  rejects replacement and identity-less directories, and removes only when
  `RemoveDirectory` confirms emptiness.
- Native NTFS parent-directory flush succeeds with a writable directory handle;
  injected refusal remains an honest per-operation durability warning.
- No-op drift cannot refresh identity, last-seen, hash, or correspondence.
- Multi-GiB simulated copy cancellation and pause occur within one configured
  chunk; pause persists completed status, emits no terminal, releases custody,
  and resume performs fresh preflight at the back of the queue.
- Progress totals equal copy/update content bytes exactly and remain monotonic;
  event rate stays under the configured bound.
- Transient sharing violations retry within bound, including update replace and
  move-update old-to-trash failures after an earlier sub-step committed;
  persistent locks fail with actionable `sharing-violation` rather than false
  drift/occupancy and do not hang the session.
- Copy-stream evidence is tagged `copy`, target identity comes from post-publish
  stat, and `last_verified_at` remains unchanged until real verification.
- Recorder failure test preserves the successful filesystem result, reports the
  ledger-behind condition, and permits later reconciliation.
- All volume locks and open handles release on success, refusal, cancel, policy
  stop, recorder failure, and unexpected exception.
- Immediate rerun after success, crash recovery, or partial failure converges to
  an accurate no-op/remaining-work plan.
- Import-linter proves executor imports core but no sibling module.
