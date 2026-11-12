# M1 Maintenance Refactor — Completed Delivery Record

**Status: complete (2026-08-11).** This is the retained decision and delivery
record for maintenance-refactor checkpoints 1–15, not an active implementation
plan. Active behavior and future work are governed by the focused architecture,
module, and M1-stage documents.

## Summary

The work began from `0817cad`. It did not invalidate the refactor, but added one
ownership requirement: UPDATE backup copying and its open-handle drift checks
belong in executor `native.py`, while `runtime.py` translates native drift facts
into the existing `OperationFailure` contract.

The delivered work proceeded in three stages:

1. Correct the known policy deviations in isolated, documented bug-fix commits.
2. Consolidate shared root authority and executor settlement policy.
3. Perform behavior-preserving package splits and test consolidation.

Public behavior, serialized plans, fingerprints, database schemas, event
ordering, error vocabulary, and executor imports remain compatible except for
the explicitly identified safety fixes.

## Completion status and final decisions

All fifteen checkpoints are complete. Checkpoints 8–15 closed in `2b38407`;
the preceding authority and safety checkpoints had already landed before that
structural series. The immediate adversarial follow-up is also complete at
`dd5677b`:

- `8a3d64e` made verifier authority-bound opening an explicit protocol and
  kept selection/opened-volume policy in the engine.
- `824055f` made ordinary collaborator exceptions terminalize active executor
  effects and pending directories before re-raising, and made supplied runtime
  roots fail closed when they differ from reviewed authority.
- `5abf08a` added the missing observer, cleanup, and collaborator-exit oracle
  coverage; `0c4d9a9` separately replaced the reviewed baseline; `767c5e8`
  and `dd5677b` reconciled the delivery and baseline-lineage documentation.

The public-facade settlement oracle is a retained maintenance asset, not a
temporary differential harness. Keep
`tools/executor_settlement_audit.py` and
`tools/executor_settlement_baseline.json` for later executor/verifier work.
The current reviewed gate covers 30 scenarios and 70 exact policy rows; run
`python -m tools.executor_settlement_audit check --repeat 3`. Its baseline was
replaced only in the dedicated `0c4d9a9` review commit after isolated fixes,
independent expectations, and three stable captures.
Its current Git blob is `97ebd0a37264dd52989f23ccd36358fbe67886e0` and its
canonical-JSON semantic pin is
`df69bf65979c3838e3df9bcc262cd9961945e6a8603c348c22f8136f4d6547b2`.

Final recorded verification is `1568 passed, 2 skipped`, import lint `11 kept,
0 broken`, compileall, `git diff --check`, and the three-run retained-oracle
gate. `docs/TOOLS.md` and `docs/EXECUTOR.md` govern current oracle use;
`docs/HANDOFF.md` records only the latest operational context.

## Contracts and boundaries

### Shared root authority

Add an unpersisted core contract:

```python
@dataclass(frozen=True, slots=True)
class RootAuthority:
    logical_root: str
    reviewed_anchor: str | None
    expected_volume_id: VolumeId | None
```

- Plan-derived authority uses the fingerprinted `Root.path`, matching `VolumeId`, and reviewed `VolumeEvidence.device_id`.
- Inventory-derived authority uses `VolumeResolution.root_path`, its current `selected_mount`, and `LocationBinding.volume_id`.
- It is fresh evidence for a particular check, never cached authorization.
- It does not alter plan JSON, fingerprints, payload versions, `LocationBinding`, or database schemas.
- Core owns typed probe facts/failures and no-follow component walking; modules retain responsibility for mapping those facts into warnings, refusals, exceptions, or outcomes.
- Planner remains lexical/topological only. No `RelativePath` migration or planner filesystem authority is introduced.

### Executor package

```text
namisync/modules/executor/
    __init__.py
    runtime.py
    native.py
    pipeline.py
```

Dependencies:

```text
__init__ -> runtime, native, pipeline
runtime  -> native, pipeline
native   -> core + stdlib
pipeline -> core + stdlib
```

`native.py` and `pipeline.py` remain mutually independent and never import `runtime.py`.

The facade explicitly preserves existing imports, including:

- `execute`
- `BoundedFailurePolicy`, `ExecutorPolicies`
- `OperationFailure`, `SystemClock`
- `NativeFileSystem`, `UnsafeExecutionPath`
- `NativeCopyBackend`, `CopyPipelineMetrics`

Compatibility covers import paths, signatures, exceptions, outcomes, and behavior; private symbol locations and class `__module__` values are not compatibility guarantees.

For `0817cad` specifically:

- `MANAGED_FILE_ATTRIBUTE_MASK` remains core policy.
- DOS-device alias handling remains pure pathing policy.
- UPDATE backup copying remains a serial, hashless native operation and is not routed through `pipeline.py`.
- Native code owns the pre/post handle-stat matcher and raises a private typed drift fact. Runtime immediately translates it to the current `TARGET_DRIFT` `OperationFailure`, preserving the exact existing reason and messages.
- A small full-write loop may exist independently in native and pipeline rather than coupling the two modules.

### Typed effect journal

Runtime replaces the parallel dictionaries with one private journal entry per operation:

- Optional typed byte effect for COPY, UPDATE, or MOVE_UPDATE.
- Optional typed mutation effect for MOVE, RECASE, TRASH, DELETE, UPDATE-readonly, or MKDIR.
- Retry error and owned temporary path.
- Explicit install, retain, snapshot, settle, retire, and temporary-path claim/release operations.

A pure settlement reducer receives typed publication and mutation verdicts plus terminal cause. Filesystem probes remain outside it.

Policy remains:

- Confirmed publication is authoritative and suppresses subordinate readonly evidence.
- Otherwise publication and sibling mutation evidence are both classified.
- Unchanged mutation does not degrade an outcome.
- Durable, ambiguous, or unreadable mutation evidence degrades recording.
- Ordinary failures retain their original reason.
- Cancellation retains the existing `canceled-after-*` vocabulary.
- Byte settlement remains the primary detail; sibling mutation state uses `mutation_durable_state`.
- No failed or canceled operation produces success evidence.

### Verifier

Give verifier a coarser package boundary:

```text
namisync/modules/verifier/
    __init__.py
    engine.py
    native.py
```

- `engine.py`: classification, orchestration, progress, and a small pure recording-settlement reducer.
- `native.py`: Windows unbuffered reading, handle work, volume checks, and final-path-by-handle checks.
- Keep item verification and post-copy verification as separate flows.
- Move the executor/verifier hasher lifecycle helpers into the existing core evidence layer.
- Preserve current verifier public imports through `__init__.py`.
- Production contexts carry one optional `RootAuthority`; when present, every selected item must match its exact logical root. Unbound mode remains only for injected fake/custom readers.

## Delivered checkpoints (all complete)

The checkpoint descriptions retain their original scope and acceptance gates.
Where they use future tense, read them as delivered work; the completion record
above resolves later decisions that changed the original plan.

### 1. Establish rules before restructuring

Update `AGENTS.md` and `docs/ARCHITECTURE.md` first:

- Permit internal imports within a domain component package while retaining independence between planner, scanner, preflight, executor, and verifier.
- Record the executor and verifier ownership boundaries and dependency graphs.
- Define root authority as ephemeral evidence, not persisted identity or durable authorization.
- State that final-touch authority checks and multi-file scheduling belong to executor runtime.
- State that single-file throughput belongs to pipeline and Windows I/O flags belong to native.
- Record the journal/reducer distinction: observation performs I/O; reduction is pure policy.

Replace the import-linter wildcard module prohibition with component-level independence. Internal executor/verifier constraints are added when those packages exist.

Gate: import lint, documentation consistency search, full suite.

### 2. Fix ordinary-failure sibling settlement

Before structural work, fix the confirmed current gap where an unverified UPDATE publication suppresses retained readonly mutation evidence.

- Make ordinary failure compose both evidence channels unless publication is confirmed, matching cancellation policy.
- Add one focused persistent regression.
- Update the executor defect ledger and policy documentation.
- Do not otherwise refactor settlement in this commit.

Gate: focused publication/readonly/retry/cancellation tests, full executor tests.

### 3. Introduce the core root-authority substrate

- Add `RootAuthority`, typed probe observations/failures, no-follow component walking, and shared reparse/directory classification.
- Move native anchor/volume probing out of pure lexical pathing behind a temporary compatibility re-export.
- Preserve all existing consumer behavior at this checkpoint.
- Add one compact core matrix covering drive, UNC, folder-mount anchors, volume changes, intermediate/final reparses, missing components, and long paths.

Gate: core/pathing tests, fingerprint and payload golden tests, import lint.

### 4. Fix scoped scanner admission

- PATHS and SUBTREES inspect every relative component before touching the leaf or starting enumeration.
- Unsafe/unavailable intermediates stop that subject and produce the existing typed incomplete result.
- Missing intermediates retain absent/disappeared semantics.
- The FULL folder-mount-root exception remains restricted to the exact FULL root.

Add focused persistent regression coverage and update scanner/BUGS documentation.

### 5. Bind preflight to reviewed authority

- Compare the reviewed anchor with a fresh current anchor as well as checking volume identity.
- Walk subject, parent, temporary, and trash components without following reparses before resolution.
- Preserve pure preflight as the sole verdict policy layer.
- Preserve current mappings for missing subjects, unavailable roots, unavailable observations, and trash refusals.
- Perform no later probe after an authority rejection.

Add focused persistent regressions and update preflight/BUGS documentation.

### 6. Bind verifier selections to one exact root

- Replace the split context anchor/volume fields with optional `RootAuthority`.
- Production standalone and post-copy workflows always provide it.
- Reject a mismatched selection root before opening the reader or emitting durable evidence.
- Preserve opened-handle volume identity, final-path-by-handle, share mode, no-buffering, and per-item revalidation.

Add focused persistent regressions and update verifier/BUGS documentation.

### 7. Consolidate remaining non-executor authority users

Migrate scanner, inventory, sync workflows, preflight, and verifier to the shared core probe contracts.

- Preserve inventory ambiguity and location-admission policy in workflows.
- Derive inventory authority from the current `VolumeResolution`, never a stale selected mount.
- Preserve each module’s existing timing and outcome mapping.
- Do not move DB alias-follow placement behavior or planner topology policy into root authority.

Gate: scanner, inventory, preflight, verifier, and workflow suites plus import lint.

### 8. Atomically split the executor package

Perform the file-to-package conversion in one commit; do not leave both `executor.py` and `executor/`.

- Move code by ownership without altering branch order, retry timing, or syscall timing.
- Preserve facade imports through `__init__.py`.
- Apply the `0817cad` backup-drift ownership adapter described above.
- Update tests to patch the owning module:
  - pipeline queues, threads, backpressure, sizing, and diagnostics;
  - native Win32 bindings, paths, handles, ACLs, metadata, and backup copying;
  - runtime attestation, operation decisions, retries, and settlement.
- Add import-linter constraints enforcing the package dependency graph.
- Update executor documentation to describe the three files.

Gate: facade signature snapshot, executor/pipeline/ACL/integration tests, import lint, compile check.

### 9. Apply shared root authority to executor native

- Runtime derives source and target authorities from the reviewed plan.
- Native adapts those authorities into fresh Windows probes.
- Preserve every current guard location, including the final check immediately before mutation.
- Preserve operation-specific absence/version/trash and final-touch choreography.
- Do not add successful-path probes, cache check results, or treat a checked path as a durable capability.

Gate: root swap, anchor/volume change, reparse, trash, long-path, and final-touch race suites.

### 10. Introduce the typed effect journal

- Replace the parallel continuation, mutation-attempt, retry-error, and temporary-path dictionaries with `_EffectJournal`.
- Retain the corrected existing classifiers and settlement branching during this commit.
- Ensure a journal entry is discarded only after terminal settlement completes.
- Preserve prepared-byte reuse, retry counts, sleep/control behavior, recorder calls, flush timing, and temporary cleanup.

Use the retained public-facade settlement oracle to compare normalized outcomes,
events, recorder calls, retries, and filesystem traces against the corrected
baseline. It remains in `tools/`; do not delete it after this checkpoint.

### 11. Introduce the settlement reducer

- Add typed publication, mutation, and terminal-cause verdicts.
- Make probes observational only and the reducer responsible for precedence, degradation, reason/detail selection, and recording disposition.
- Route ordinary failure, cancellation, and deferred MKDIR finalization through it.
- Keep a compact permanent reducer matrix, replacing equivalent operation-local assertions rather than adding another full test layer.
- Update executor and architecture documentation.

Gate: full executor suite plus the retained oracle. Preserve the oracle and its
reviewed baseline after parity is established.

### 12. Consolidate shared evidence and verifier recording

- Move exact hasher construction/update/finalization helpers into core evidence code for use by pipeline and verifier.
- Add a small pure verifier recording-settlement reducer.
- Preserve distinct item and post-copy outcome construction.
- Replace duplicated verifier recording assertions with a compact matrix.

Gate: evidence, pipeline, verifier, and post-copy suites.

### 13. Atomically split the verifier package

- Move native reader mechanics into `native.py` and orchestration into `engine.py`.
- Preserve public imports through `__init__.py`.
- Update patches to their owning module and separate native-reader tests from engine tests.
- Add import-linter rules preventing native from importing engine or other domain components.

Gate: complete verifier suite, workflow integration tests, import lint.

### 14. Consolidate tests around stable boundaries

- Organize executor tests by runtime, native, pipeline, and settlement.
- Centralize fault builders, sharing-violation construction, outcome extraction, recorder assertions, readonly setup, and pause/cancel latches.
- Parameterize repeated operation/state matrices.
- Move generic authority cases to the core matrix while retaining adapter-specific outcome and call-timing tests.
- Preserve every distinct mutation race, final-touch check, recorder consequence, and cancellation boundary.

The original three-regression growth target was superseded when the
public-facade oracle was retained and post-refactor hardening added distinct
safety cases. Consolidation still replaces duplicated scaffolding and
equivalent local assertions; it must never remove a distinct mutation race,
final-touch guard, recorder consequence, cancellation boundary, or oracle row
merely to reduce test count.

### 15. Remove compatibility shims and close documentation

After all consumers have migrated:

- Remove duplicate Win32 anchor/volume implementations and the temporary pathing compatibility export.
- Search for stale references to monolithic executor/verifier files and old patch targets.
- Reconcile focused module documentation and `ARCHITECTURE.md`.
- Add one compact README hardening/refactor changelog entry.
- Replace `docs/HANDOFF.md` with final verification and operational context.

Gate: complete suite, import lint, compile check, `git diff --check`, and an adversarial review for hidden behavior changes and boundary violations.

## Regression and acceptance evidence

The following gates were run at corrected-baseline, package-split,
authority-complete, journal-complete, verifier-complete, and final checkpoints:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\lint-imports.exe
.\.venv\Scripts\python.exe -m compileall -q namisync tests
git diff --check
```

Baseline evidence at `0817cad`:

- Targeted executor/pathing run: 484 passed.
- Import contracts: 8 kept, 0 broken.
- Repository handoff baseline: 1,354 passed, 2 skipped.

Final acceptance was established with:

- Existing executor and verifier public imports and signatures remain usable.
- No plan, fingerprint, payload, evidence, event, or database schema changes.
- Except for separately reviewed, documented safety corrections and their
  dedicated baseline replacement, normalized outcomes, details, event order,
  recorder calls, retry/control behavior, and filesystem call timing match the
  applicable corrected baseline.
- Pipeline never publishes, records, retries, interprets operations, or imports native/runtime.
- Native never imports runtime or pipeline.
- Root-authority observations are always fresh at the existing policy boundary and are never cached as authorization.
- Every operation has at most one journal entry with independently representable byte and mutation effects.
- No additional executor split is considered during this work.
- Future single-file throughput work can be implemented primarily in pipeline; Windows flags remain native; multi-file/per-volume scheduling remains runtime.

## Explicit exclusions

- No rollback of the cited bug-fix commits.
- No further executor or verifier subdivision.
- No throughput, queue-policy, multi-file scheduling, or per-volume concurrency changes.
- No handle-relative traversal redesign or new root-directory identity guarantee.
- No `RelativePath` value object or persisted root-authority record.
- No planner filesystem authority, DB path-policy redesign, or globally permitted reparse traversal.
- No opportunistic cleanup outside code and tests made redundant by this refactor.
