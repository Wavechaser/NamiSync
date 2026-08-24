# Executor Module

Status: M1 Stages 2 and 4 implemented. The native executor covers every reviewed
operation kind on local Windows filesystems. Normal copies use one bounded
reader/hasher/writer pipeline at a time, fixed adaptive chunks, XXH3-128
evidence, measured conditional preallocation, and single-handle native
finalization. Successful byte-producing operations now publish exact
continuation evidence for optional in-session readback. External writers remain
outside NamiSync's volume-lock contract; the residual races are documented
below rather than presented as closed.

## Accepted Recording-Settlement Target (Not Active)

The activation sequence and exact result/event shapes are owned by
[M1_BRIDGE.md](M1_BRIDGE.md). Executor's local target is operation-local typed
recording attribution: one recorder failure can lower the aggregate floor but
cannot label another operation degraded or convert filesystem success into
filesystem failure. Task-scoped recording issues preserve first observation
order and never rewrite a settled item or suppress committed evidence.

Publication evidence remains success-only and process-local. It may support
immediate linked readback and pause/resume, but it is neither ledger/history
state nor desktop presentation data and must be gone before terminal session
publication. Exact continuation custody and omission witnesses are specified
by the bridge plan.

The settlement oracle remains the change gate. Typed projection must preserve
its protected scenario/row manifest, normalized filesystem and recorder
traces, baseline, and semantic hash. Structural settlement work stays blocked
until three identical runs and independent review pass. The oracle owns its
scenario manifest, [M1_SHELL_H2.md](M1_SHELL_H2.md) owns checkpoint coverage,
and [TESTS.md](TESTS.md) owns test-scope policy; none is duplicated here.

## Purpose

The executor is the only module that applies a reviewed `ExecutionSet` to
managed user data. It implements plan operations exactly, enforces final guards,
publishes content atomically where the platform permits, emits progress/item
events, and records successful evidence through `Recorder` only after the
filesystem result exists.

It does not scan, plan, choose conflict resolutions, infer new destinations,
write SQL, own volume locks, prompt a human, or treat a policy callback as an
alternate execution engine.

## Component Package

`namisync.modules.executor` is a stable public facade over three ownership
files. `runtime.py` owns operation dispatch and policy, final-touch guards,
retries, continuations, cancellation, recording, settlement, progress, and
outcomes. `native.py` owns Windows filesystem primitives, metadata, handles,
publication, trash, and root-authority adaptation. `pipeline.py` owns the
bounded one-file read/hash/write flow, queues, backpressure, teardown, metrics,
and `CopyDigest` production.

Runtime may import both leaves. Native and pipeline are mutually independent,
never import runtime, and do not import sibling domain components. Code outside
the executor imports this package facade; tests that patch an internal detail
patch the file that owns it. Acceptance tests mirror the boundary in
`test_executor_runtime.py`, `test_executor_native.py`,
`test_executor_pipeline.py`, and `test_executor_settlement.py`; the focused ACL
contract remains in `test_executor_acl.py`.

## Entry Contract

```python
execute(xset, ctx, recorder, policies, fs) -> OperationResult
```

The caller holds deterministic physical-volume custody and validates the exact
core `Commitment` defined by [M1_BRIDGE.md](M1_BRIDGE.md). Execution admission
cannot resupply or reinterpret frozen setup choices. Workflow alone performs a
fresh observe → preflight → execute sequence
on every start/resume; executor imports no preflight sibling. A refusal permits
no temp cleanup or other mutation. After a successful verdict, workflow passes
preflight's touched-target-parent scope to the executor filesystem for one exact
prior-run temp sweep, then processes dependency-ready operations in plan order.
A sweep failure stops before any planned operation is admitted.

The core generic session runner emits the single terminal event. Executor emits
phase, progress, and item outcomes only, returns one complete
`OperationResult`, and never emits the terminal projection. Event-v5 detail,
scalar, omission, and envelope rules are centralized in
[M1_BRIDGE.md](M1_BRIDGE.md). `Canceled`/`PauseRequested` unwind to the runner
after executor's own safe operation-boundary cleanup.

## Universal Operation Rules

- Checkpoint before each operation and at operation-specific safe boundaries.
- At each operation's point of touch, revalidate its direct source/target
  preconditions against live filesystem evidence: expected identity/type/stat,
  required absence/occupancy, root containment, and directory emptiness where
  relevant. Drift fails that operation without guessing.
- Validate paths lexically and by resolved handle; use long-path-safe APIs.
- Keep plan, continuation, recorder, diagnostic, and returned `Path` values in
  ordinary absolute drive/UNC spelling. `NativeFileSystem` introduces the
  extended-length prefix only at Windows resolution, observation, stream,
  mutation, metadata, volume, and flush calls; containment comparisons use the
  logical spelling on both sides.
- Use operation-matched conditional primitives where Windows provides them:
  `CREATE_NEW` for temps, non-replacing rename when destination absence is a
  precondition, and `RemoveDirectory` for atomic nonempty refusal. Never follow
  a reparse escape.
- Flush recorder before every operation's final destructive guards so recorder
  contention cannot sit between the last source/destination observation and
  UPDATE, DELETE, MOVE, RECASE, MOVE_UPDATE cleanup, or TRASH mutation.
  UPDATE places that wait before its final backup, prepared-temp, source, and
  live-target validation. After any such barrier, an operation touching owned
  trash revalidates the exact run-owned destination plus every existing parent
  for containment, ordinary-directory/reparse state, and target-volume identity
  before inspecting or mutating the leaf.
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
live name. `DEFENSE.md` makes full preservation conditional on managed-root
quiescence and classifies this post-final-guard path as EW-3; the residual must
remain visible in tests and documentation rather than becoming a false compare-
and-swap guarantee.

## Copy State Machine

1. Validate expected source and destination states.
2. Create an exclusive exact-name temp in the final target parent and volume.
   At or above the measured private 8 MiB threshold, request exactly the
   reviewed allocation without advancing logical EOF. Only explicitly
   unsupported allocation falls back; disk-full, quota, permission, and
   unknown errors fail before streaming.
3. Open the source through the cached `O_SEQUENTIAL` path. Select a fixed
   256 KiB chunk below 8 MiB, 1 MiB below 32 MiB, or 4 MiB thereafter, capped
   by `ExecutorPolicies.max_chunk_size`.
4. Stream immutable chunks through caller/reader → hasher → writer under one
   combined 32 MiB payload budget and 32-item caps on both FIFOs. The hasher
   and writer are the only workers; the caller admits reads, checkpoints, and
   reports progress only after hash and full write complete in FIFO order.
   Every file size, including empty and 4 KiB, uses this same pipeline.
5. Close the content writer without flushing it. Open one finalization handle
   before any opted-in ACL is copied, apply normalized creation/mtime/access and
   managed attributes while withholding readonly, issue exactly one
   `FlushFileBuffers` on that held handle, and retain its normalized stat.
   ACL failure fails before publish. ADS remains outside the state machine.
6. Require the digest byte count to equal the reviewed size, then re-stat the
   source. Drift fails and removes the exact current-owned temp; no attestation
   is recorded.
7. Re-check destination expected absence/state at publish and use a conditional
   atomic primitive appropriate to the planned before-state.
8. Atomically publish with the Windows/local-filesystem primitive.
9. Compare one post-publish target stat with the normalized temp baseline.
   Before attestation, require matching kind and size plus stable identity when
   the target profile supplies it. Repair and flush only fields publication
   changed, including name-tunneled creation time or deferred readonly;
   otherwise perform no target metadata write, target reopen, or second file
   flush. The same observed stat is reused for this binding, the size guard,
   and attestation, so the check adds no filesystem call.
10. Require the published target size to equal the hashed byte count before any
    operation-specific destructive completion step. MOVE_UPDATE builds the
    attestation at this point, so an attestation-construction failure cannot
    move the reviewed old path to trash. COPY and UPDATE defer attestation until
    their filesystem completion and durability work finishes.
11. Complete the operation-specific filesystem work, including UPDATE's
    hardlink-backup metadata or MOVE_UPDATE's old-to-trash rename, then open
    every affected parent directory with `GENERIC_WRITE` and
    `FILE_FLAG_BACKUP_SEMANTICS`, then attempt best-effort flushes. A refused or
    unsupported flush is a per-operation durability warning; the result claims
    durability only for what was actually flushed. Construct or reuse
    `Attestation(ContentEvidence("xxh3_128", ...), target_stat)` in the safe
    operation-specific order so target identity remains distinct from source
    identity.
12. Call recorder. A successful COPY/UPDATE/MOVE_UPDATE transaction returns the
    actual target inventory row/location/scope/path identity; idempotent replay
    returns that same tuple. A recorder failure preserves the filesystem
    outcome, leaves the published evidence rowless, and degrades
    `RecordingStatus` instead of relabeling the copy as failed.
13. Emit exactly one reliable `ItemOutcome`, then store its operation status and
    any `PublishedCopyEvidence` in `ExecutionSet`. Continuation state therefore
    cannot claim a settled item whose reliable outcome failed to publish. Only
    COPY/UPDATE/MOVE_UPDATE produce published evidence; failed, no-op,
    metadata-only, and unreached operations never do. If reliable delivery
    itself fails after an effect, the exception backstop cleans and retires the
    process-local effect without manufacturing continuation settlement.

Temps use `<name>.synctmp-<run-id>-<op-id>` with validated fixed-format ids.
Once per successfully preflighted execution, recovery enumerates only direct
children of the same touched target parents used for capacity accounting. It
removes exact-grammar regular files whose embedded run id differs from the
current run; current-run temps remain under per-operation retry/cancel cleanup.
Recovery never recurses, enters `.synctrash`, or deletes a substring lookalike.

## Update And Trash-On-Update

An update completely prepares the replacement temp before backup/publication,
then revalidates it after the recorder wait and before replacing the current
target. With trash-on-update enabled it:

1. validates/reserves `.synctrash/<run-id>/<relative-path>` on the target volume;
2. preserves the old live file there using a same-volume hardlink when
   `CapabilityProfile.supports_hardlinks`; otherwise writes a trash-local exact
   temp from one open source handle. The handle stat must match the reviewed
   live-target snapshot before copying; the copied byte count and a second stat
   of that same handle must still match before metadata is finalized from the
   bound snapshot and the backup publishes atomically. Growth, truncation, or
   visible same-size drift fails as `target-drift`; a failed prepublication copy
   revalidates the owned parent chain before removing its temp;
3. flushes prior recorder evidence after backup preparation but before any
   final publication validation, then revalidates the complete owned-trash
   parent chain again;
4. captures or revalidates backup evidence and then performs the final backup,
   prepared-temp, source, and live-target guards; a hardlink defers metadata
   repair because it still shares the live inode;
5. clears readonly on the live target if Windows requires it for replacement;
6. atomically publishes the prepared temp over the live path with `os.replace`;
7. applies the new file's readonly bit and remaining post-publish metadata;
8. validates and completes hardlink-backup metadata after the replacement, then
   performs the best-effort parent flushes, constructs the attestation, and
   records success.

Every operation first binds both logical roots to the full source/target
`VolumeId` and any reviewed mount anchor carried by the plan. Source and target
authority is rechecked after recorder, copy, or retry boundaries before a
source predicate can authorize work or a retained target path can be touched.
NOOP uses the same binding before recording correspondence, and trash parents
are not created until the reviewed target root is re-admitted.

Runtime derives each ephemeral `RootAuthority` directly from the fingerprinted
plan root and reviewed volume facts at the existing guard. Native injects its
process-cached Windows bindings into fresh anchor/volume probes and supplies
the legacy executor component classifier to the shared core admission walk,
then maps typed failures back to the existing `UnsafeExecutionPath` and native
error vocabulary. Chain-only admission still omits a volume probe when the
plan carries no expected `VolumeId`; no observation is cached or treated as
authorization for a later touch.
The operational root passed to a source or target guard must also lexically
equal that authority's logical root before any probe or path resolution. This
prevents a caller from validating the reviewed plan root and then touching a
different supplied root.

When changed content also carries an opted-in basename casing change, this same
required update publishes at the source-spelled basename. Metadata-equal casing
changes use the zero-byte recase operation below instead of copying content or
creating an update trash entry.

No crash point leaves the live path absent. A crash after hardlink creation but
before replacement leaves the old live inode with link count two; that is a
benign, scan-visible hardlink warning which disables move detection until the
trash link is purged. Rerun reconciliation distinguishes exact owned temp/run
backup/already-published state from unrelated user files and converges without
discarding the only known-good version.

The planner/preflight formula includes backup-copy bytes on no-hardlink targets.
A partial backup remains under exact temp grammar, is ignored by restore
planning, and remains with the trash run directory until a future reviewed
maintenance purge; ordinary temp recovery still never walks `.synctrash`.
Readonly ordering/recovery restores the old version's planned attributes after
replacement so the hardlinked trash inode is not left silently degraded.

Backup creation never redefines the accepted live target version. UPDATE keeps
the pre-backup stat across retries, permits only its own hardlink's expected
link-count increment, and rechecks that evidence before copied-backup repair and
replacement. A swap during backup creation therefore fails as target drift
without overwriting the external bytes.

The final guard cannot make the subsequent path-based replacement conditional
on target identity. If an external process swaps the live target after backup
and guard but before replacement, that external file can be replaced without
being the version preserved in trash. NamiSync still records only the
post-publish target it actually created, so the ledger is not falsely attached
to the displaced object. `DEFENSE.md` classifies this as EW-3. Tests assert the
data consequence and settlement, never a timing-based safety claim.

## Other Operations

### Recase

Flush pending recorder state, validate the reviewed source and old target, and
require the old and requested paths to share one Windows path key while
differing in exact spelling before the same-volume non-replacing rename. On
ordinary case-insensitive NTFS the destination aliases the source object and the rename
updates only its directory-entry spelling. On a case-sensitive target a
distinct occupied destination makes the primitive fail without overwrite. The
executor flushes the parent, re-stats the same file, and records the new target
spelling and correspondence only when the post-rename stat still identifies the
reviewed old target version. The recorder repeats that version check
defensively. It transfers zero bytes, preserves file identity and metadata,
creates no trash entry, and never recases parent directories.

### Move

Flush pending recorder state, then revalidate the reviewed source-tree subject,
old target, and new destination; refuse occupancy; and perform a same-volume
non-replacing atomic rename whose
primitive itself fails if the destination appeared. After best-effort
parent-directory flushes, stat the result and require it to remain the reviewed
old target version before recording correspondence. The recorder repeats that
version check defensively; it does not replace it with exact comparison against
source metadata that planning intentionally treats as equal within target
timestamp granularity. A vanished or drifted source subject, or a vanished or
swapped old target, yields a typed failed outcome and must not create a stale
mapping claim.

### Composite move-update

Publish the changed content at the new path first, then flush pending recorder
state and revalidate the old path plus the complete owned-trash destination
chain before trashing the old path. Every attempt, including recovery after a
committed rename, revalidates that chain before inspecting the trash leaf. An
already-completed retry needs no second pre-mutation flush. One plan
operation may have internal prepare/publish/trash stages, but only one
final outcome and ledger transition. A crash after any internal stage may leave
both old and new versions, never neither, and leaves no completed mapping claim.

### Mkdir

Create only the planned directory after revalidating the reviewed source
directory, parent containment, and expected target absence. Existing matching
directories may converge to a typed no-op; the create primitive must atomically
fail if a new entry appeared, and wrong-type entries fail. Apply source
directory attributes and restore directory timestamps only after all descendant
child operations have settled.
Every created directory has its own reviewed mkdir-with-metadata operation from
an all-directory `DirRecord`; executor never creates implicit parent paths.

### Trash

Resolve trash under the target on the same physical volume, create guarded run
parents, refuse reparse/off-volume paths, flush pending recorder state, and then
revalidate the lexical target root and every existing trash parent immediately
before the source/leaf guards and rename. Use a non-replacing rename that fails
atomically on trash collision. Never degrade to copy-delete. Record only after
the rename succeeds.

### Delete and directory cleanup

Mirror deletion remains internal/guarded. Re-stat type and identity immediately
before deletion, after flushing prior recorder evidence, and use the strongest
available handle-conditional delete.
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

Pipeline admission checks cancel/pause between reads and while every bounded
queue operation waits, so at most one further read is admitted after a
stage-observed request. Either request aborts both workers, joins them, releases
the complete byte budget, and unwinds rather than blocking. First-error storage
preserves one original worker/callback/control exception instead of leaking a
queue-shutdown artifact. Executor catches `Canceled` only long enough to inspect
any process-local durable retry continuation before cleanup and emit reliable
outcomes for the in-flight and unreached selection, then re-raises for runner
aggregation and the one canceled terminal. After those outcomes it forces one
inactive progress snapshot, so time throttling cannot leave a settled operation
presented as still running at the terminal boundary. The snapshot comes from
authoritative live reporter state: it includes every reliably settled item and
the current aggregate byte high-water, while clearing the four nominal item
fields and `current_path`. A
prepared-but-unpublished operation remains `CANCELED`; an unfinished operation
whose target already published is
`FAILED` with `canceled-after-publish`, structured on-disk-state detail,
degraded recording, and no success-only published evidence. The classifier
prefers the continuation's synchronous publish flag and cached post-repair stat.
Otherwise an intact matching owned temp proves the publish did not occur even
if the target changed independently; consumed temp plus a present target is the
committed-but-raised fallback. Truly unverified byte state fails with its
drift/I/O reason and does not by itself claim publication or degrade recording.
Cancellation still settles an independent mutation marker: exact restored
pre-state retains the byte result, while changed, ambiguous, or unreadable
readonly/non-byte state becomes `canceled-after-mutation` and degrades
recording. Combined detail preserves byte `publish_state`, `durable_state`, and
probe error fields while naming marker durability as `mutation_durable_state`.
UPDATE deletes only the staged temp and reports a backup as `retained` only when
its current version matches the continuation's creation or repaired evidence;
replacement, absence, and read failure are reported as `changed`, `absent`, or
`unverified`. Backup and MOVE_UPDATE trash paths in result detail are
target-root-relative rather than machine-specific absolute paths. Before
repaired evidence exists, an identity-weak profile cannot distinguish a
same-kind/same-size backup substitution. MOVE_UPDATE distinguishes new+old from
new+trash; neither is rolled back. Ordinary pause abandons/reclaims an in-flight
temp through exact-name recovery, preserves completed `ExecutionSet` statuses
and aggregate byte high-water, forces pause-drain recording plus one fresh
authoritative live progress snapshot, and re-raises without terminal;
dispatcher then releases custody. That snapshot retains the paused item's
identity, path, and current attempt counters while exposing the live aggregate
byte high-water and every reliable settlement, including a directory finalized
during the unwind. Deferred directory finalization cannot replace the paused
item's progress identity.
Resume queues at the back, freshly re-observes/preflights in workflow, and
continues only unreached work.
Direct `PauseRequested` and process-fatal `BaseException` unwinds attempt exact
owned-temp cleanup but preserve the original control or exception and emit no
terminal item from executor. A cleanup failure on those paths may leave the
exact-name temp for fresh-run recovery; these unwind semantics are outside the
terminal settlement reducer rather than being converted into an item result.
An ordinary `Exception` escaping a failure policy, retry/control callback,
event sink, or other collaborator is different: before propagating it, runtime
settles every active journal effect from the original operation failure,
finalizes pending directories, and retires already-recorded effects without
replaying their filesystem or recorder actions.

The same durable-state rule applies when a confirmed publish is followed by a
non-cancellation failure such as metadata repair exhaustion. The item remains
`FAILED` under its underlying typed reason, reports whether the target is still
the published version plus any retained UPDATE backup or MOVE_UPDATE old/trash
state, and sets `recording=DEGRADED` because no success ledger command
completed. A confirmed or unverified durable mutation never reports
`recording=OK` and never becomes verification evidence. If the durable-state
probe itself fails, publication is reported unverified and recording still
degrades instead of claiming the ledger is current.
Ordinary failure snapshots retained byte and mutation effects exactly once
before owned-temp cleanup. A cleanup failure decorates that snapshot without
probing again or replacing the underlying operation reason; when no durable or
unverified effect exists, the existing `cleanup-failed` result remains.

MOVE, RECASE, TRASH, DELETE, MKDIR, and readonly clearing in UPDATE/DELETE keep
a lightweight process-local mutation marker from immediately before their first
mutation until recording or truthful failure settlement. A synchronous return
confirms the mutation; a raised primitive or later failure uses only
failure-path stats to prove the captured pre-state unchanged or to classify
committed, ambiguous, or unreadable state. Exact unchanged state keeps the
ordinary failure and recording status. Any durable or unverified mutation is
`FAILED`, recording-degraded, and has no success evidence; cancellation uses
`canceled-after-mutation`. MKDIR retains the marker through deferred metadata;
resumed-directory restoration has its own failure probe. Case-insensitive path
stats cannot prove a failed RECASE's exact spelling, so that state degrades
conservatively. These markers and probes add no filesystem operation to
successful execution. Ordinary failure and cancellation evaluate the byte
continuation and mutation marker independently unless byte publication is
confirmed. Confirmed publication remains the authoritative failed-publish or
`canceled-after-publish` result. When byte classification is unverified,
publication diagnostics stay primary, marker durability is named
`mutation_durable_state`, and a failed byte classifier cannot short-circuit
marker settlement. A pre-publication UPDATE backup is also byte-channel state:
when it remains in owned trash, ordinary failure and cancellation retain its
path, method, and observed state as primary detail while independently naming
any readonly mutation. Confirmed publication remains authoritative and
suppresses that subordinate marker even when the retained backup is reported.

Runtime now stores those process-local facts in one private typed effect journal
entry per operation. The entry independently holds a COPY/UPDATE/MOVE_UPDATE
byte continuation, a non-byte mutation marker, the last retry error, and an
optional owned temporary path. Failure and cancellation take one immutable
snapshot before cleanup; owned-temp cleanup releases the claim before deletion,
and terminal item settlement completes before the entry is retired. A retry
error or temporary claim alone is not a durable effect and therefore does not
latch pause. Runtime observers now perform the failure-only filesystem probes
and return typed publication and mutation verdicts. One pure reducer consumes
those verdicts plus an ordinary-failure or cancellation cause; it alone selects
precedence, outcome/reason vocabulary, detail composition, and recording
degradation. Ordinary failure, cancellation, and both immediate and deferred
MKDIR failures use that same reduction path. Confirmed publication suppresses
subordinate mutation evidence; otherwise unchanged mutation is ignored while
durable, ambiguous, and unreadable mutation classifications degrade recording.
The reducer performs no I/O, does not mutate its verdict inputs, and cannot emit
published success evidence. A compact direct policy matrix owns those reduction
axes while operation tests retain filesystem-probe and call-timing coverage.

## Settlement Stability Gate

Settlement refactoring is blocked on an independent retained oracle, not only
on differential parity with the current implementation. Its scenario manifest
states expected terminal outcome, reason, recording disposition, durable-state
classification, recorder/flush behavior, retry/control behavior, cleanup, and
filesystem trace through public executor and core contracts. A corrected
baseline is eligible for structural work only when every scenario is
classified, none is skipped or expected to fail, three consecutive normalized
runs are byte-identical, the committed snapshot has no diff, and an adversarial
review has no unresolved settlement finding.

A newly exposed policy defect is fixed in its own commit with a persistent
regression before the baseline is regenerated; that change resets the
three-run gate. The oracle and its committed baseline remain under `tools/`
through the executor split, typed journal, reducer, verifier split, and final
test consolidation. They are intentionally not temporary checkpoint artifacts:
the original 58 rows retain corrected-monolith attribution through the
refactor, while the 12 later rows retain separately reviewed post-refactor
stabilization behavior. Together they form the current corrected-baseline
lineage for later regression checks.

The retained baseline is `tools/executor_settlement_baseline.json`, currently
with oracle `format_version: 1`. The resume gate is exactly:

```powershell
.\.venv\Scripts\python.exe -m tools.executor_settlement_audit check --repeat 3
```

For the current 30-scenario, 70-row manifest, success ends with
`settlement check passed: 30 scenarios x 3 runs`. The command is read-only: it
requires all independent policy expectations, three byte-identical normalized
captures, and exact manifest/trace parity with the clean baseline at `HEAD`.
The canonical JSON must also match the separately reviewed semantic SHA-256
pinned in the tool, so a staged, worktree-only, or unpinned committed baseline
replacement cannot satisfy the official gate. A non-default `--baseline` check
is labeled as an unpinned diagnostic and is not a resume gate. Package split,
journal, reducer, verifier-split, and immediate stabilization commits must not
edit or regenerate that baseline. Only a separately reviewed and documented
settlement-policy fix may replace it after its focused regression lands. The
replacement baseline and its semantic pin then land together in one dedicated,
reviewed baseline-replacement commit before the three-run gate is restarted.

The normalized trace projects the version-4 Progress phase, nominal item and
attempt state, attempt-local counters, and the execution continuation's byte
high-water and fixed selected-byte admission. Random attempt tokens are never
erased from the authority merely to stabilize the snapshot: each token observed
in a Progress event is replaced by a deterministic first-seen ordinal while its
phase and nominal owner are retained, and reuse under a different owner fails
the capture. A retired token may not reappear. The pause/resume row retains each
invocation's v4 Progress and execution byte authority rather than projecting
only the final continuation. Reporter transition tests remain the detailed
attempt-state authority; the oracle records their integrated visibility across
all settlement policies. Independent global invariants also require final
Progress `items_done` to equal the number of emitted reliable terminal item
outcomes,
require its aggregate byte fields to equal the live `ExecutionSet` authority,
and forbid terminal or exceptional-unwind activity from surviving after
settlement.

Fixture fault injection is fail-closed: every installed rule must fire its
declared number of times. The cleanup matrix includes the failed pre-retry temp
cleanup regression, requiring `cleanup-failed` settlement before retry sleep or
another control checkpoint while retaining the exact-name partial temp for
fresh-run recovery.

The retained observer rows classify restored MOVE/TRASH/DELETE subjects, a
disappeared committed MKDIR, unreadable DELETE/UPDATE probes, and changed,
missing, or unreadable targets after confirmed publication. Separate
collaborator rows prove that a committed MOVE still settles from the original
operation error if failure policy or retry sleep raises, and that a pending
MKDIR finalizes if the next checkpoint raises. Those injected `RuntimeError`s
remain externally visible; unused collaborator injections fail the fixture.

Published evidence is executor continuation state, not a second inventory
selection. It round-trips exact post-publish stat/content/provenance plus the
copy-recording result across a same-process execute pause. If status reaches
`SUCCEEDED` without evidence, the compound workflow reports a named
verification-incomplete invariant failure rather than silently omitting
readback.

Sharing violations use bounded retry with injected clock/backoff and checkpoints
between attempts. COPY, UPDATE, and MOVE_UPDATE install an operation-local stage
continuation once their prepared bytes or backup/publish state must survive a
retry. They revalidate the prepared/published file and owned backup/trash, resume
at publish, replace, metadata repair, or old-to-trash rename, and recognize the
exact committed state if an injected/native boundary reports failure after the
syscall took effect. No guarded retry recopies the main payload, and UPDATE's
copy-backup continuation is installed only after that backup exists. All three
byte-producing operations then use one completion path for the resumed-target
guard, target metadata/stat, size guard, operation-safe attestation/filesystem
ordering, directory durability, and recording; their tails cannot silently
drift into separate implementations. MOVE_UPDATE attests before its destructive
old-to-trash finish; COPY and UPDATE attest after their operation-specific
completion/durability boundary.

Non-byte mutation markers likewise survive a retry until the operation proves
its exact pre-state unchanged or reports the durable/ambiguous mutation. Pause
is latched while either a byte continuation or mutation marker is live, so it
cannot discard process-local settlement evidence; cancellation inspects that
evidence and composes both state channels immediately.

When a retryable failure occurs before either retained-state channel exists,
owned-temp cleanup must succeed before retry sleep or another control
checkpoint. Cleanup failure terminates that item as `cleanup-failed`; it cannot
be discarded and then reclassified as a plain cancellation while the temp
remains for exact-name recovery.

Every retry attempt that begins with an already-published continuation performs
one target stat before any remaining metadata repair, durability, attestation,
or recording. The current profiled file version must match the cached published
stat. Before that stat exists, kind/size and stable identity bind the prepared
publication when identity is available, while mtime remains repairable
metadata. A missing or identity-detectable replacement fails as `target-drift`
with no recorder call or published evidence. Normal first-pass execution
performs no extra stat. On an identity-weak profile, the pre-cache guard cannot
distinguish a same-size replacement. Even with stable identity, same-object byte
mutation that preserves the observed size/metadata is not detected; closing
either boundary requires a handle-bound publication protocol or rereading
bytes. This check is neither.

Pause observed at a retry-backoff checkpoint while either retained state is live
is latched until that operation settles, then raised at the ordinary operation
boundary. Cancellation is never latched and preempts a pending pause. If the
settling failure policy returns `Stop`, that terminal policy decision suppresses
the pause: later operations settle `policy-stop`, with pause ignored but a
cancel checkpoint before each status emission so a large sweep remains
interruptible. The production sharing policy contributes at most 350 ms of
retry sleep (50 + 100 + 200 ms). This is not a hard elapsed-time bound:
remaining latency is filesystem durability/metadata/rename and recorder I/O
over already-staged data. Custom injected policies own their own sleep budget.
Persistent failure records `sharing-violation` after the configured bound and
independent work continues. Unexpected executor exceptions are contained by the
session wrapper, release custody, and never suppress already-earned outcomes.
Their settlement backstop likewise clears and force-emits terminal progress;
an event-sink failure that prevents that emission is attached to the original
exception rather than replacing it.

## Progress

The shared version-4 field meanings, transition authority, and recovery rules
are owned centrally by `ARCHITECTURE.md` §2.3. This section records only the
executor's implementation of that protocol.

Executor `Progress` snapshots use `phase=execute` and carry aggregate content
bytes/items, the display-only current path, and `operation` item identity while
an operation is active.
The item identity is the current execution spotlight, not the set of every
operation awaiting reliable settlement. A successfully created directory
leaves that spotlight when its create step returns, while its outcome and
`items_done` increment remain deferred until descendant work and directory
metadata finalization complete. That inactive handoff keeps the directory as
the informational `current_path`, clears all item/attempt fields, and uses the
ordinary lossy throttle; a later operation may therefore replace it before a
consumer observes the inactive snapshot. Reporter activation rejects an
in-process attempt to overwrite an operation that is still active.
Non-byte operations and byte operations that have not entered the copy stream
carry no attempt id or item-byte counters. At the exact copy-backend entry, a
byte operation mints a fresh opaque 32-lowercase-hex attempt id and starts at
`0 / content_bytes`; chunk callbacks advance that attempt-local counter up to
the reviewed total. If a backend reports more stream bytes than the reviewed
total, the operation and attempt identities stay active but both item-byte
counters become null; the executor neither fabricates a larger admission nor
lets the aggregate exceed reviewed content. Reliable settlement clears the
item identity, attempt id, and item-byte counters; ordinary intermediate
settlement may retain `current_path` as display-only telemetry.
Normal completion force-emits the live totals/path and inactive item
fields after reliable settlement, independently of the ordinary time throttle.
Cancellation and an escaping-exception backstop likewise force a snapshot from
authoritative live reporter state after reliable unwind settlement. It carries
the live item totals and aggregate byte high-water while clearing
`current_path` and the five nominal item/attempt fields, so the terminal snapshot
neither fabricates unfinished activity nor contradicts work completed inside a
throttle interval.

A retry resets attempt-local bytes only if `_prepare_copy` actually re-enters
the byte pipeline. Retained publication, metadata, durability, attestation, and
recording continuations bypass that entry and do not reset. If an abandoned
attempt reported bytes, the reset snapshot is forced past the normal time
throttle. Aggregate executor bytes never regress: they hold their high-water
mark until the new attempt catches up, persist through the strict workflow
continuation, and seed the resumed reporter before any new stream begins. A
terminally failed item reports that high-water mark rather than rewinding it.
A canceled or escaping-failure unwind exposes the live item-settlement count
and aggregate byte high-water while clearing item activity and display path.
Pause force-emits the complete live reporter state without clearing the active
item, attempt id/bytes, or display path; its aggregate high-water is also
retained in the execution continuation for resume. Resumed byte-pipeline entry
mints a new attempt id and starts that attempt at zero. Retained publication,
metadata, durability, attestation, and recording continuations do not mint a
replacement attempt id because they do not re-enter the byte pipeline. Moves,
trash, mkdir, delete, and no-op contribute items but
zero transfer bytes. Emission remains throttled/coalesced outside forced
control boundaries so fast disks cannot flood UI queues.

## Copy Pipeline Diagnostics

`NativeCopyBackend` can collect a diagnostic snapshot for performance tests and
investigation without changing copy behavior:

```python
backend = NativeCopyBackend(
    hasher_factory=hasher_factory,
    collect_metrics=True,
)
digest = backend.copy(...)
metrics = backend.last_metrics
```

Collection is disabled by default. With `collect_metrics=False`, `last_metrics`
is `None` and the pipeline does not sample its diagnostic clock. Each valid copy
invocation clears the prior snapshot; when collection is enabled, cleanup
publishes one immutable `CopyPipelineMetrics` snapshot even if the started
pipeline is canceled or fails.

The snapshot contains:

- `reader_blocked_seconds`: time the coordinator waited for byte-budget
  capacity or a bounded pipeline queue to accept the next item;
- `writer_starved_seconds`: time the writer waited for an item from its input
  queue;
- `payload_high_water`: the greatest reserved payload byte count during that
  copy; and
- `reserved_bytes`: the reservation remaining after worker cleanup. A completed
  or aborted copy must return this to zero; a nonzero value is a pipeline
  accounting defect.

These metrics describe pipeline backpressure, not user-facing throughput, ETA,
or durable run telemetry. They are neither emitted as progress events nor
recorded in the ledger/history, and no interface should derive transfer status
or scheduling policy from them. The 32 MiB combined payload budget and the
fixed adaptive chunk bands remain executor-private constants.

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
- File-level concurrency has no current setting or protocol. It may return only
  after a workload benchmark demonstrates underutilization and the resulting
  design preserves capacity, deterministic outcome aggregation, and
  per-volume safety; Stage 1 deliberately removed `worker_count` without a
  replacement.
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

## M1 Stage 2 Implementation

`namisync/core/execution.py` owns `ExecutionSet`, validated run identifiers,
typed executor reasons and decisions, and the filesystem/copy/recorder
protocols. The `namisync.modules.executor` facade supplies `NativeFileSystem`,
`NativeCopyBackend`, `BoundedFailurePolicy`, `ExecutorPolicies`, and `execute`
from the owning package files described above. Pipeline consumes a required
parameterless hasher factory and delegates construction, update, finalization,
and raw-digest validation to the shared core evidence lifecycle. It has no
third-party or sibling-module import; workflow composition owns the sole
concrete `xxhash.xxh3_128` object and supplies the reviewed, freshly preflighted
set. Dispatcher/session owns custody and terminal aggregation, and the
run-bound recorder owns durable ledger interpretation.

The Stage 2 suite re-proves all nine operation kinds through the new path and
pins every gate in `obsolete/M1_HASH_REFACTOR.md` §4.5: stage overlap and FIFO/byte bounds;
exact first-error teardown; growth/shrink, cancellation, pause, and callback
paths; adaptive-band wiring; allocation allowlist; exact temp grammar and
recovery isolation; one finalization handle/flush; conditional repair;
published-size guards for copy/update/move-update; copy-backup boundaries; and
the complete move-update stage-fault matrix. The factory/evidence tests also
prove copy→ledger→Windows-unbuffered verify round-trip, raw 16-byte digest
contracts, repository reconstruction, and preservation of SHA-256 identity
hashes. Workflow/dispatcher/recorder suites retain the responsibilities that
belong outside this module, including fresh preflight, custody, one terminal,
durable run-token idempotency, and independent recording/audit status.

The final production-shaped benchmark ran all five standard corpora from
`F:` NAND to separate `G:` NAND, `E:` Optane, and `J:` HDD targets. It records
operations/s, throughput, fixed finalization time, stage starvation, payload
high-water, legacy serial comparisons, and the allocation sweep in
`obsolete/M1_HASH_REFACTOR.md` §2.8. The measured 8 MiB allocation threshold and adaptive
chunk bands remain private constants, not settings.

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
- A no-hardlink backup binds the reviewed live-target stat to one open handle,
  rejects pre-copy mismatch or post-copy growth/truncation/same-size metadata
  drift, removes the unpublished temp, and performs neither backup publication
  nor live replacement. Stable copying preserves the exact bytes and bound
  metadata before the ordinary final target guards run.
- Source mutation during any chunk or before final stat fails the operation and
  records no digest/attestation.
- Opt-in ACL copy failure fails before publish and leaves the prior live target
  untouched. A real restrictive-DACL test proves the held finalization handle
  still sets basic information and flushes after a fresh metadata reopen is
  denied. ADS preservation is available through the semantic-settings facade,
  but has no separate real-filesystem acceptance case in this suite.
- Target appearance/change after preflight but before mutation is detected by
  the final guard when it occurs before that guard. Faults injected between
  guard and touch prove only the condition owned by the mutation primitive:
  non-replacing rename rejects destination appearance and `RemoveDirectory`
  rejects nonempty directories. Source-object swaps are rejected only by an
  explicitly handle-bound mutation; otherwise they remain inside the EW-1
  through EW-4 external-writer classes in `DEFENSE.md`. Update fault injection
  proves an external swap may
  replace the swapped file without trashing it but cannot publish partial bytes.
  A prepared-temp substitution during UPDATE's recorder flush is rejected by
  the post-flush guard, and a stable-identity temp substitution between guard
  and publish is rejected by the cached post-publish observation before
  attestation. Identity-weak and same-object mutation remain the disclosed
  non-handle-bound boundary.
- First blocked/failed work does not abort later independent operations; broken
  dependents receive explicit outcomes.
- Exact temp recovery removes prior-run regular files only from preflight's
  touched-parent scope; current-run temps, substring lookalikes, exact-name
  directories, untouched parents, off-volume mounts, and `.synctrash` survive.
  Cleanup failure stops before copy allocation or publication after preflight
  credited those bytes.
- Trash is refused when its final destination-chain guard observes a reparse,
  cross-volume path, or collision, and never degrades to copy-delete. A parent
  substitution after that guard remains the disclosed path-to-rename residual
  and may preserve bytes outside owned trash.
- Move occupancy, vanished/drifted source, vanished-old-path, wrong type,
  post-rename substitution, and retained-missing-row cases produce correct
  filesystem and recorder outcomes without rolling back other earned records.
- Recase preserves target identity/metadata and requested basename spelling,
  transfers zero bytes, creates no trash, rejects source/old-target drift and
  post-rename substitution, and cannot overwrite a distinct destination.
- Directory create/delete tests cover full chains, wrong types, nonempty races,
  vanished source directories, no recursive unplanned deletion, and metadata
  application only after every child operation has settled; every created empty
  or non-empty directory comes from its own reviewed `DirRecord` operation.
- Same-run trash/move cleanup tolerates only directory mtime/link-count churn,
  rejects replacement and identity-less directories, and removes only when
  `RemoveDirectory` confirms emptiness.
- Native NTFS parent-directory flush succeeds with a writable directory handle;
  injected refusal remains an honest per-operation durability warning.
- No-op drift cannot refresh identity, last-seen, hash, or correspondence.
- Stage-synchronized multi-GiB cancellation and pause admit at most one further
  read, join both workers, and release the full byte budget; pause persists
  completed status, emits no terminal, releases custody, and resume performs
  fresh preflight at the back of the queue.
- Progress totals equal reviewed copy/update content bytes exactly and remain
  monotonic; an over-reporting backend makes only the active item counter
  indeterminate, and event rate stays under the configured bound.
- Transient sharing violations retry within bound, including update replace and
  move-update old-to-trash failures after an earlier sub-step committed;
  persistent locks fail with actionable `sharing-violation` rather than false
  drift/occupancy and do not hang the session.
- MOVE/RECASE/TRASH/DELETE/MKDIR commit-then-raise, unchanged pre-commit,
  ambiguous two-path, and failed-probe cases report recording truth without
  success evidence. Deferred/resumed mkdir metadata, readonly UPDATE/DELETE
  restoration, and non-byte retry pause/cancel retain the same guarantee.
- Readonly UPDATE retry cancellation composes unavailable byte-publication
  state with restored or changed marker state, preserves confirmed-publication
  authority, and records no false evidence.
- COPY/UPDATE/MOVE_UPDATE metadata and durability retry faults reject a
  same-size/same-mtime replacement of an already-published stable-identity
  target as `target-drift`, retain the foreign bytes, and record no false
  success evidence.
- Copy-stream evidence is tagged `copy`, target identity comes from post-publish
  stat, and `last_verified_at` remains unchanged until real verification.
- Recorder failure test preserves the successful filesystem result, reports the
  ledger-behind condition, and permits later reconciliation.
- All volume locks and open handles release on success, refusal, cancel, policy
  stop, recorder failure, and unexpected exception.
- Immediate rerun after success, crash recovery, or partial failure converges to
  an accurate no-op/remaining-work plan.
- Import-linter proves executor imports core but no sibling module.
