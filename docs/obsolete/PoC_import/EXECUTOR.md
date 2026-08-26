# NamiSync Executor

## Current Scope

The executor is a pure core component. It consumes a confirmed `SyncPlan`,
validates operation-relevant paths against the plan snapshots, and performs
filesystem operations only when touched paths still match the plan. It does not
call Qt, write to SQLite, or combine planner/database behavior.

The database commit rule is unchanged: orchestration code must record DB state
only after executor filesystem operations return, and DB failure must not mask
the real `RunResult`.

## Phase 2 workflow boundary

The pure executor has no SQLite or mutex code. The application workflow obtains
ordered physical-volume guards before executor preflight, holds them through
filesystem mutation and main-ledger recording, then releases them before the
independent history write. A mapping-scoped run uses the same executor token as
the run record and `.synctrash` path. Copy/update/move results update physical
target inventory only after filesystem success.

## Module

- `namisync/core/executor.py`
  - `execute_plan(plan, run_id, progress_callback=None, cancel_requested=None)`

## Supported Operations

- `copy`: copy source file to target.
- `update`: replace target with source.
- `move`: move an existing target-side file from its old relative path to its
  new relative path.
- `mkdir`: create a source-only empty directory tree on the target.
- `trash`: move target-only file into `.synctrash/<run-id>/<relpath>`.
- `delete`: remove target file for internal `mirror` plans.
- `noop`: record skipped success.
- `conflict` or any blocked operation: record a failed operation instead of
  guessing.

The executor continues after failed or blocked operations where it can. The
returned `RunResult.success` is false if any operation failed, but later
independent operations still get a chance to complete. The application workflow
records that partial result in both the main ledger and `history.db`; the GUI
keeps the per-operation failures visible rather than presenting the run as a
clean success.

Core progress events carry cumulative and per-file byte counts, not computed
speed or ETA. The GUI derives an average rate/countdown and keeps explicit
calculating placeholders visible until byte progress exists. A future progress
pass may replace this with rolling, phase-aware estimates.

Before capacity or stale-path checks, the executor refuses a plan whose scans
were incomplete. A partial scan is reviewable, never executable, because it
cannot safely establish source-only or target-only state.

Before stale-plan validation, the executor repeats the planner's target free
space check. It refuses the run before any mutation when the target no longer
has room for all new copies plus every temporary update file, or when the
volume cannot be inspected.

Before execution, the executor stats only paths touched by planned operations:
copy/update source files, copy/update targets, move sources and destinations,
trash/delete targets, and mkdir source/target directories. Changes to those
paths fail the run with a `preflight` result before temp cleanup or any planned
operation. The caller should treat that as "pause and scan/plan again."
Unrelated changes elsewhere in either tree do not veto the run.

Preflight understands the planner's `move` then `update` sequence: an update
whose target will be created by a preceding move validates that the target path
is still absent before execution, then lets the move operation create it.

Preflight is a stale-plan mitigation, not a lock. Changes can still land after
preflight and before an operation. The per-operation guards are the final
guarantee: no overwrite on unexpected move/copy targets, directory type checks,
and directory emptiness checks immediately before directory trash/delete.

Phase 2 adds an orchestration-level cross-process physical-volume guard before
this existing preflight; see "Locked Phase 2 guard" below. The pure executor
does not acquire DB or Qt locks itself.

## Copy Safety

Copy and update operations write to a temporary file beside the final target:

```text
<name>.synctmp-<run-id>-<operation-id>
```

The executor copies bytes, flushes and fsyncs the temp file, copies source
metadata to the temp file, then uses `os.replace()` to atomically publish the
final target path on the same volume.

The same source-byte stream feeds a SHA-256 digest for each successful `copy`
and `update`. That digest is passed to state recording only after the atomic
rename succeeds. It records what the source stream contained; it is not a
write-readback verification of the target medium.

If copying fails, the temp file is removed where possible.

After publishing a temp file with `os.replace()`, the executor attempts a
best-effort parent-directory fsync. Directory fsync may not be supported on all
Windows paths, so failure to fsync the directory is not treated as operation
failure.

Before a run starts, the executor checks only parent directories touched by a
planned copy or update and removes files matching NamiSync's exact generated
temp-name shape. It does not perform another full target-tree walk, does not enter
`.synctrash`, and does not delete user files that merely contain `.synctmp-`.
This handles relevant temp files left by crashes, hard kills, or power loss;
orphans elsewhere remain until a later plan touches their parent directory.

## Move Safety

Move operations are target-side only. The executor resolves
`PlanOperation.move_source_rel_path` and `PlanOperation.target_rel_path` under
the target root, creates the destination parent directory, and uses
`os.replace()` to move the file on the target volume.

The executor checks that the destination does not already exist before calling
`os.replace()`. After a move, it attempts best-effort parent-directory fsyncs
for both the old and new parent directories.

Move-plus-update is not one filesystem transaction in the MVP. If a crash lands
after the target-side rename but before the follow-up copy/update, the target
may temporarily contain old content at the new path while the DB row says the
file is present. A later fresh scan/plan compares metadata and schedules the
needed update.

Phase 2 execution recording rekeys an executor-confirmed move's physical
location-file row in place. Because NamiSync performed the move, this does not
need scanner inference or a new hash. The stable row id, hash,
`hash_observed_at`, and `last_verified_at` are preserved.

## Trash Safety

Trash operations move target files to:

```text
.synctrash/<run-id>/<relpath>
```

The relative path is preserved. A different `run_id` creates a separate trash
namespace.

There is one `.synctrash` directory directly under each target root, never one
per source subdirectory. Before a trash move, the executor resolves that
directory and refuses it if it escapes the target root through a symlink or
junction, or if it is not on the target root's physical volume. A permitted
trash move is therefore an `os.replace()` rename on the target volume, not a
copy-and-delete operation.

After trash and delete operations, the executor attempts best-effort
parent-directory fsyncs for the affected directories.

For empty directory operations, `mkdir` creates a planned source-only empty
directory leaf and any missing ancestors, `trash` moves an empty target-only
directory tree to `.synctrash/<run-id>/`, and `delete` removes an empty
target-only directory tree with guarded `rmdir()` calls. If earlier file trash
operations already created the matching trash directory, directory trash
removes the now-empty target directory after confirming the trash destination
exists. Directory trash/delete refuses to act if files are found inside the
directory at execution time. The planner avoids directory cleanup for
directories containing ignored files, so ignored files are left alone instead
of being deleted as a side effect.

## Path Safety

Executor paths are resolved under the plan roots. Empty paths,
drive-qualified paths, absolute relative paths, paths containing `..`, and
paths that resolve outside their root fail the run.

The MVP uses normal `pathlib`/Python Windows paths and has not yet added an
explicit `\\?\` long-path layer or verified the packaged executable's long-path
manifest behavior. Deep-path support therefore remains a hardening requirement,
not a completed safety claim.

## Progress And Cancellation

`execute_plan()` accepts an optional progress callback. It emits
`ProgressEvent` values before and after each operation.

`execute_plan()` also accepts an optional cancellation callback. Cancellation is
checked before each operation and between 1 MiB chunks during file copies.
Cancellation still cannot interrupt every underlying OS call, but large copies
are no longer forced to run to completion before cancellation is observed.

## Result

The executor returns `RunResult`:

- `success`
- `canceled`
- `operations`
- `bytes_done`
- `bytes_total`

Per-operation status is represented by `OperationResult`.
The byte counters measure transferred copy/update content only. Same-volume
move, trash, and delete metadata operations do not inflate transfer progress or
ETA.

## Phase 2 physical-volume guard

Before capacity/stale-plan preflight, orchestration resolves the source and
target to stable Windows physical-volume identities and acquires exclusive
named cross-process mutexes in sorted identity order. A same-volume pair is
acquired once. The guard is held through filesystem execution and successful
main-ledger recording, then released before the independent history write.

If a required volume identity is unknown or already held, execution is refused
or deferred with an action-guiding message. It never falls back to unlocked
mutation. OS ownership releases mutexes after process failure. This
conservatively blocks disjoint work on one physical disk and intentionally
forms the safety seam for a later disk-affinity scheduler; network-share
coordination remains out of scope.

Main-ledger sync runs also persist the executor `run_token`. The same token is
used for the trash namespace and history idempotency, but neither database has
a foreign key to the other.

## Tests

Executor coverage lives in:

- `tests/test_executor.py`
- `tests/test_phase2_hardening.py`
- `tests/test_volume_guard.py`

Current tests cover:

- copy, update, move, trash, and noop execution.
- planner-produced move-then-update execution.
- empty directory mkdir/trash execution.
- touched-path preflight refusal before filesystem mutation.
- unrelated source/target changes not blocking execution.
- internal mirror delete.
- missing move/trash/delete targets as preflight failures.
- existing move destination refusal.
- continuing after failed and blocked operations.
- cross-process same-volume contention across disjoint folders and recovery
  after the lock-holder process exits unexpectedly.
- temp cleanup after copy failure.
- precise orphaned temp cleanup in copy/update parent directories.
- unsafe relative path rejection, including drive-qualified paths.
- existing trash destination refusal.
- blocked operation refusal.
- cancellation before the next operation and during copy.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest
```
