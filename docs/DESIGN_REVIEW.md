# NamiSync Design Review

Status: draft findings from reconciling `FEATURES.md`, `ARCHITECTURE.md`, and
`PoC_import/BUGS.md`. This file records unresolved contract questions; it does
not override either authoritative source.

## Severity

- **M0 blocker**: resolve before the walking skeleton mutates user files.
- **Milestone blocker**: resolve before the named later feature is implemented.
- **Documentation defect**: the intended behavior is inferable, but the source
  contract should be corrected before implementation depends on it.

## M0 Blockers

### DR-01 — Mandatory review conflicts with unattended execution

`FEATURES.md` says every sync has a dry-run review, and the current product
direction says human review remains mandatory between plan generation and
committing execution. `ARCHITECTURE.md` nevertheless defines
`run_unattended_sync()` and unattended ingest as a single session with no gate.

Required decision: either remove no-gate execution or define a durable,
explicit preauthorization whose scope, plan fingerprint, expiry, and material
change policy count as the review commitment. A generic CLI flag must not waive
the safety invariant.

### DR-02 — Pause cannot both block and release custody

`Checkpoint.__call__()` says it blocks while paused. The session model says a
pause drains to a boundary, releases all volume locks, and always re-preflights
on resume. A blocked workflow stack cannot safely release custody and later
resume through a fresh preflight without making the checkpoint domain-aware.

Recommended direction: checkpoint raises a typed `PauseRequested` at a safe
boundary; the generic session runner persists/retains an opaque continuation
request, exits the workflow, releases locks, and resume starts a new guarded
continuation. Define which module serializes remaining execution state.

### DR-03 — Exactly-one-terminal ownership is misplaced

The executor is assigned the single-`Terminal` guarantee, but scan, plan,
verify, baseline, import, maintenance, and dummy sessions also require exactly
one terminal event. If both executor and dispatcher wrappers emit terminals,
duplicates are likely.

Recommended direction: the generic session runner owns terminal emission in
one `finally`; modules return typed results and never emit `Terminal` directly.

### DR-04 — Planner lacks prior correspondence evidence

The pure signature accepts source scan, target scan, options, and scope. That is
insufficient for source-identity rename detection: the planner must know which
source identity corresponded to which target path in the prior accepted state.
The PoC lost move evidence when no-op correspondence was not persisted.

Required change: add an immutable `MappingSnapshot`/correspondence input from a
repository. It must include paired no-ops, retained missing rows, normalized
keys, and ambiguity/hardlink evidence.

### DR-05 — Pure planner has no capacity input

`Plan.target_free_space` and capacity planning are planner outputs, but the
planner is pure and its signature supplies neither free space nor a capacity
snapshot. Direct `disk_usage()` inside the PoC planner was already identified
as a robustness and duplicated-formula bug.

Required change: pass an immutable `PlanningCapacity` observation into the
planner, or remove observed free space from `Plan` and compute it in a separate
review observation. The required-byte formula remains a pure shared function.

### DR-06 — Filter-drift comparison has no current value

The plan carries `filter_snapshot`, but `preflight(xset, world)` has no current
filter/settings snapshot to compare against. `ObservedWorld` contains only
filesystem observations.

Required change: include semantic configuration in `ExecutionSet` or a
separate immutable `ExecutionEnvironment`; do not read mutable settings inside
pure preflight.

### DR-07 — Attestation identity is ambiguous after copy

`Attestation` has one `file_identity`. A copy-stream digest attests source
bytes, while the durable ledger row describes the newly published target,
whose filesystem identity differs. Persisting the source identity on the
target would corrupt move and drift evidence.

Required change: distinguish content evidence from subject stat evidence, or
construct the final attestation from the digest plus a post-publish target
stat. The source stat remains separate drift evidence.

### DR-08 — Trash-on-update is not transactionally atomic

The proposed update moves the current target to trash before publishing its
replacement. A crash between those operations leaves the live target missing.
The same problem exists inside composite move-update. Deferring the ledger write
prevents a lie but does not preserve availability or per-operation atomicity.

Required decision: define a recoverable update state machine, preferably using
a fully prepared temp plus a Windows replacement primitive with a same-volume
backup where possible. Specify exact startup/rerun reconciliation for every
crash point and never automatically delete the only good version.

### DR-09 — Reliable, non-blocking, bounded delivery is underspecified

Reliable events may never be dropped, and a slow subscriber may never stall
the producer. A bounded in-memory queue cannot guarantee both. M0's
keep-everything replay buffer is also unbounded.

Required decision: choose a limit policy—durable spill, subscriber failure with
an explicit gap, bounded session admission, or controlled backpressure. History
cannot be described as guaranteed audit if its reliable stream may disappear
silently.

### DR-10 — Volume label is evidence, not stable identity

`VolumeId` includes label, while known-volume recognition is described as
serial-driven and automatic. Labels can change; cloned serials can collide.

Required change: separate stable key material from mutable corroborating
evidence. Define matching rules for label changes, filesystem reformats,
serial clones, and simultaneous ambiguous mounts.

### DR-11 — Unsupported scan entries have no typed representation

Placeholders must be recorded as `unsupported` without being opened, but
`FileRecord` has no support/entry-state field and warnings alone cannot carry a
reviewable candidate through inventory and planning.

Required change: add a typed support state or a separate unsupported-entry
record. Planner behavior must be explicit: blocked/reviewable, never silently
ignored and never executable.

### DR-12 — Parent-directory durability wording conflicts

Architecture calls parent-directory fsync a bone; Features calls it best
effort. Windows directory flushing can fail or be unsupported depending on the
handle/filesystem.

Required decision: define the Windows durability guarantee and how an
unsupported/failed directory flush affects operation outcome and user-visible
warnings. Do not claim power-loss atomicity beyond what was actually flushed.

### DR-13 — M0 cross-process volume custody is unclear

Features require deterministic cross-process physical-volume locks. The M0
dispatcher explicitly defers queue-owner persistence but does not clearly say
whether volume locks are real cross-process locks or merely in-process
scheduling. A safe CLI cannot ship with only in-process mutation exclusion.

Required decision: keep durable queue ownership in M2, but require real
cross-process volume locks before the M0 executor can mutate user data.

### DR-21 — `ObservedWorld.stats` cannot distinguish roots

The architecture types it as `Mapping[str, FileStat | None]`. Source and target
normally have the same relative path, so a string key is ambiguous and can make
preflight compare an operation against the wrong side.

Required change: key observations by a typed `(root role/root id, rel_path_key)`
subject or operation evidence id. Never concatenate strings with an ad hoc
separator.

### DR-22 — Metadata preservation has no evidence shape

Features promise preservation of standard attributes, creation time, ADS where
supported, and optional ACL/owner policy. `FileRecord` and `PlanOperation` as
described carry only size/mtime/identity/link count, so review, preflight, and
executor cannot agree on what metadata was observed or intended.

Required change: define a typed metadata snapshot and preservation policy in the
plan. Decide how unsupported ADS, stream copy failure, creation time, readonly
publish ordering, and ACL opt-in affect outcomes.

## M1 And Persistence Blockers

### DR-14 — Integrity outcomes do not fit the generic event type

`ItemOutcome.outcome` is the five-value generic `Outcome`, while verifier
consumers need verified, baselined, mismatched, modified, missing, unsupported,
canceled, and error. Encoding these as free-form `kind` or `reason` strings
would recreate the PoC's inconsistent presentation paths.

Required change: add a typed integrity result inside event detail or define a
typed event body dedicated to integrity while retaining generic delivery class.

### DR-15 — Recorder failure and terminal status are not fully defined

The recorder must fail loudly, yet a bookkeeping failure must not rewrite a
successful filesystem result as though the copy failed. It is unclear whether
the session terminal is `COMPLETED`, `FAILED`, or a successful result with a
durability warning when the ledger is behind.

Required change: define separate filesystem outcome, recording outcome, and
session status aggregation. The UI/history must tell the truth about both.

### DR-16 — History is optional telemetry and required audit at once

History failures never roll back real work and telemetry may be missed
silently, but every explicit run is described as history-worthy and history is
the audit trail. These are different guarantees.

Required decision: classify history as best-effort activity telemetry or a
required audit record. In either case, observer failure must be surfaced and
must not falsify the filesystem/ledger result.

### DR-17 — Session-store retention semantics are missing

`SessionStore.drop()` exists, while the session table is also the source of
truth for task/status views. The contract does not say when terminal sessions
are dropped, retained, or handed off to history.

Required change: define terminal retention, queue discard, compaction, and the
relationship between session records, GUI tasks, and audit history.

## Later-Milestone Blockers

### DR-18 — Ingest idempotency and policy snapshots are incomplete

Stateless resume promises to recognize collision-suffixed prior ingests using
target provenance, but the planner input and plan do not define the provenance
index, template/version fingerprint, collision assignment snapshot, or generic
annotation key namespace. Re-running after a template change could duplicate
content or choose a different suffix.

Required change before ingest: define an immutable enrichment/policy snapshot,
stable assignment algorithm, origin annotation schema, and provenance lookup
input. Execution must never recompute a destination.

### DR-19 — CLI entry-point priorities conflict

Architecture puts `sync` and `history` in M0 and desktop in M3. Features lists
no `sync` command and says all no-subcommand entry points launch the desktop.
An M0 build therefore has no defined default behavior, and the main M0 command
is absent from the feature list.

Required change: add the sync command contract, specify M0 no-subcommand
behavior, and defer GUI-default behavior until a desktop implementation exists.

### DR-20 — Metadata extractor priority text contradicts itself

Architecture says every protocol ships in M0, then says `MetadataExtractor`
ships with ingest and no extractor exists in M0. It also references a nonexistent
“§7 gap technique” when explaining the deferred `INTERRUPTED` producer.

Required change: say every M0-used protocol gets a degenerate M0 implementation;
latent protocols may be declared without one. Correct or add the missing gap
section reference.

### DR-23 — Features still assigns behavior to core

The `PROJECT ARCHITECTURE` feature bullet says core owns sync behavior. The newer
architecture and `AGENTS.md` say core owns contracts while isolated modules own
scanner/planner/executor/verifier behavior.

Required change: update the feature bullet to the newer layering so future work
does not reintroduce the old monolithic core.

## Required Review Order

1. DR-01 through DR-03: session safety and review boundary.
2. DR-04 through DR-08 plus DR-21/DR-22: plan/execution evidence and atomicity.
3. DR-09 through DR-13: custody, event durability, and platform guarantees.
4. DR-14 through DR-17 before M1 persistence/integrity work.
5. DR-18 through DR-20 and DR-23 before ingest, durable queues, or desktop release.

## PoC Bug Traceability

Every substantive entry in `PoC_import/BUGS.md` was routed to an owning draft
and a regression-oriented acceptance criterion. This table is the review index;
the module files contain the detailed criteria.

| PoC section | Owning drafts | Hardened themes |
| --- | --- | --- |
| Scanner | `SCANNER.md`, `CORE.md` | exact ignores, walk errors, cancellation, junction/reparse cycles, history DB artifacts |
| Planner | `PLANNER.md`, `PREFLIGHT.md` | full mkdir chains, same-plan directory cleanup, metadata-noop limitation, one capacity formula, observed capacity errors |
| Executor | `PREFLIGHT.md`, `EXECUTOR.md`, `RECORDER.md`, `DISPATCHER.md` | continue after independent failure, stale-plan/final guards, composite move-update, move support, chunk cancel, directory durability, empty dirs, scoped preflight, exact temp recovery, byte accounting, incomplete scans, trash volume safety, reclaimable temp capacity |
| Verifier | `VERIFIER.md`, `INVENTORY.md`, `RECORDER.md` | modified vs mismatch, explicit rebaseline, canonical selected paths, reappearance clearing, cache-honest evidence |
| Database | `DATABASE.md`, `RECORDER.md`, `INVENTORY.md`, `HISTORY.md`, `WORKFLOWS.md` | pipeline wiring, filesystem/recording truth split, actual timestamps, persisted identity, conditional writes, bounded transactions, no preview writes, all-path audit, no-op validation, canonical time, role-free inventory, composite location constraints, tombstones, serialized writer, provenance, unexpected-error audit, batched missing sweep, move collisions, writable retention, baseline/current stat separation, detail reads, skipped-move state, O(n) indexing, Windows path keys, guard preservation, paired-noop evidence, batched IO, shared host/time |
| CLI | `COMMANDLINE.md`, `INTERFACES.md`, `WORKFLOWS.md` | real argv entry points, paired ledger/history overrides, activity-aware output and exit status |
| GUI | `DESKTOP_UI.md`, `INTERFACES.md`, `DISPATCHER.md`, `WORKFLOWS.md` | scoped gating, worker/thread lifetime and affinity, layered status, native-control styling, throttled progress, cancelable import, inventory-before-integrity, typed row updates, location-only actions, partial/refused truth, toolkit ownership, context targeting, execution-to-verify handoff, stable layout, immediate metrics, safe shutdown, activity-aware history, actionable invalid input, shared actions, orthogonal plan/inventory state, scoped refresh/results, nonmodal tests |
