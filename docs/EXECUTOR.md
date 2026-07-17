# Executor Module

Status: draft contract. Priority: M0 native single-worker execution on plain
local NTFS. Atomic update recovery in DR-08 and terminal ownership in DR-03 are
blocking design decisions.

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
execute(xset, ctx, recorder, policies, fs) -> ExecResult
```

The caller must hold deterministic physical-volume custody, but executor still
validates custody/identity. Its first act is fresh `observe()` plus pure
`preflight()`. A refusal returns without temp cleanup or any other mutation.
After a successful verdict, executor may recover only exact owned temps named by
that verdict and then processes dependency-ready operations in plan order.

Per DR-03, the generic session runner should emit the single terminal event.
Executor emits phase, progress, and item outcomes and returns one complete
result. If architecture retains terminal ownership here, every non-executor
session needs an equivalent common wrapper; two owners are forbidden.

## Universal Operation Rules

- Checkpoint before each operation and at operation-specific safe boundaries.
- Re-stat every touched source/target immediately before mutation and compare
  with the plan; residual drift fails that operation without guessing.
- Validate paths lexically and by resolved handle; use long-path-safe APIs.
- Never overwrite an unexpected destination or follow a reparse escape.
- Flush recorder before a destructive operation when required by the durability
  window.
- Record one final typed outcome per selected operation; dependencies of a
  failed operation become explicit canceled/deferred outcomes, while independent
  operations continue.
- Byte progress counts copied/updated content only.
- Policies return `Continue`, `Stop`, or bounded `Retry(after)` decisions; the
  executor retains guards, limits, checkpointing, and final outcome ownership.

## Copy State Machine

1. Validate expected source and destination states.
2. Create an exclusive exact-name temp in the final target parent and volume.
3. Stream source bytes through `CopyBackend` in bounded chunks while hashing and
   checkpointing; backend writes bytes only.
4. Flush file content to the medium, apply the DR-22 typed metadata snapshot
   under explicit preservation policy, and flush again when metadata durability
   requires it.
5. Re-stat source and compare with the planned/opened source snapshot. Drift
   fails and removes/quarantines the temp; no attestation is recorded.
6. Re-check destination expected absence/state immediately before publish.
7. Atomically publish with the Windows/local-filesystem primitive.
8. Attempt the defined parent-directory durability action and report its actual
   guarantee under DR-12.
9. Stat the published target and combine it with the source-stream digest so
   target identity is never confused with source identity (DR-07).
10. Call recorder. A recorder failure preserves the filesystem outcome and is
    surfaced separately as required by DR-15.

Temps use `<name>.synctmp-<run-id>-<op-id>` with validated fixed-format ids.
Recovery is limited to exact grammar in selected copy/update parents, never a
full-tree walk and never `.synctrash`.

## Update And Trash-On-Update

An update prepares and validates the replacement temp before displacing the
current target. The old version is retained in
`.synctrash/<run-id>/<relative-path>` when trash-on-update is enabled. The exact
crash-safe replacement/backup sequence is unresolved in DR-08; implementation
must not claim operation atomicity until every point between backup and publish
has a tested recovery rule.

At minimum, no crash path may delete both old and new content, publish a partial
new file, or record final success early. Rerun reconciliation must distinguish
owned temp, owned run backup, already-published replacement, and unrelated user
files. Automatic recovery always preserves the only known good version.

## Other Operations

### Move

Revalidate old target and new destination, refuse occupancy, perform a
same-volume atomic rename, flush directory metadata according to DR-12, stat the
result, then record correspondence. A vanished source/old target yields a
typed skipped/failed outcome and must not leave the old ledger row `present`.

### Composite move-update

One plan operation may have internal prepare, move/backup, and publish stages,
but only one final outcome and ledger transition. A crash after any internal
stage leaves recoverable evidence and no completed mapping claim.

### Mkdir

Create only the planned directory after validating parent containment and
expected absence. Existing matching directories may converge to a typed no-op;
wrong-type entries fail.

### Trash

Resolve trash under the target on the same physical volume, create guarded run
parents, refuse reparse/off-volume paths, refuse destination collisions, and use
rename rather than copy-delete. Record only after the rename succeeds.

### Delete and directory cleanup

Mirror deletion remains internal/guarded. Re-stat type and identity immediately
before deletion; directories must be empty at deletion time. Never recursively
delete an unplanned subtree.

### No-op

Perform no user-data mutation. Any correspondence/last-seen recording is
conditional on both sides still matching the plan snapshot, including identity;
otherwise record a stale/skipped outcome rather than refreshing false evidence.

## Cancellation, Pause, And Failure

Copy chunks are bounded so cancel latency is bounded. Cancellation cleans or
retains owned temp according to the restart policy, marks the in-flight and
remaining operations accurately, flushes required records, and returns through
the generic session wrapper. Pause semantics depend on DR-02; M0 must not block
while pretending locks were released.

Sharing violations use bounded retry with injected clock/backoff and checkpoint
between attempts. Persistent failure records a typed reason and independent work
continues. Unexpected executor exceptions are contained by the session wrapper,
release custody, and never suppress already-earned item outcomes.

## Progress

Progress snapshots carry content bytes done/total, items done/total, current
path, phase, and optionally per-file bytes. Moves, trash, mkdir, delete, and
no-op contribute items but zero transfer bytes. Emission is throttled/coalesced
outside the copy chunk size so fast disks cannot flood UI queues.

## Expectations Of Other Modules

- Core supplies operation/evidence/result types, path guards, checkpoint, and
  policy protocols.
- Planner supplies complete immutable intent and expected before/after states;
  executor never recomputes them.
- Preflight supplies fresh verdict semantics, while executor retains final
  per-operation guards.
- Dispatcher/session runner owns physical-volume custody, pause/cancel control,
  and terminal ownership after DR-03.
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
- Throttling wraps chunk pacing without changing event semantics.
- Robocopy may supply bytes through `CopyBackend`; it never owns planning,
  trash, publish, final guards, or ledger claims.

## PoC Hardening

This contract directly covers the PoC first-failure abort, stale-plan TOCTOU,
large-copy cancellation, missing move handling, empty-directory omission,
whole-tree preflight, broad temp deletion, false byte totals, incomplete-scan
execution, cross-volume trash, orphan-temp capacity loop, missing source-drift
attestation guard, and composite move-update gap.

## Acceptance Criteria

- Fault injection before/after every state-machine step proves no partial file
  is published, no success is recorded early, and every owned artifact is
  recoverable without touching user lookalikes.
- Copy/update publish is same-volume atomic; target bytes are either the complete
  prior version or complete new version under the finalized DR-08 contract.
- Source mutation during any chunk or before final stat fails the operation and
  records no digest/attestation.
- Target appearance/change after preflight but before mutation is detected by
  the final guard and never overwritten.
- First blocked/failed work does not abort later independent operations; broken
  dependents receive explicit outcomes.
- Exact temp cleanup preserves names containing `.synctmp-`, ignores other
  directories and trash, and safely handles cleanup failure/capacity changes.
- Trash cannot escape through reparse points, cross volumes, overwrite a trash
  collision, or degrade to copy-delete.
- Move occupancy, vanished-old-path, wrong type, and retained-missing-row cases
  produce correct filesystem and recorder outcomes without rolling back other
  earned records.
- Directory create/delete tests cover full chains, wrong types, nonempty races,
  and no recursive unplanned deletion.
- No-op drift cannot refresh identity, last-seen, hash, or correspondence.
- Multi-GiB simulated copy cancellation occurs within one configured chunk;
  pause follows the finalized drain contract and releases custody.
- Progress totals equal copy/update content bytes exactly and remain monotonic;
  event rate stays under the configured bound.
- Transient sharing violations retry within bound; persistent locks skip/fail
  with actionable reason and do not hang the session.
- Copy-stream evidence is tagged `copy`, target identity comes from post-publish
  stat, and `last_verified_at` remains unchanged until real verification.
- Recorder failure test preserves the successful filesystem result, reports the
  ledger-behind condition, and permits later reconciliation.
- All volume locks and open handles release on success, refusal, cancel, policy
  stop, recorder failure, and unexpected exception.
- Immediate rerun after success, crash recovery, or partial failure converges to
  an accurate no-op/remaining-work plan.
- Import-linter proves executor imports core but no sibling module.
