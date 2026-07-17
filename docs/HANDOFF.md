# NamiSync Handoff

Date: 2026-07-18

## Session Outcome

Reviewed the reconciled `DESIGN_REVIEW.md`, `FEATURES.md`, and
`ARCHITECTURE.md`, treating Features as behavioral authority and Architecture
as contract authority. Propagated every settled, internally coherent decision
into the focused module contracts. The authoritative documents themselves were
not changed.

Updated module docs:

- `CORE.md`, `DISPATCHER.md`, and `WORKFLOWS.md`: sole core session runner,
  nonblocking checkpoint unwind, execution continuation, volume-queue resume,
  terminal retention, reliable event delivery, and two-session review/execute.
- `PLANNER.md`, `PREFLIGHT.md`, and `EXECUTOR.md`: `MappingSnapshot`, no observed
  free space in `Plan`, settings inside `ObservedWorld`, plan-and-selection
  commitment, directory-rename decomposition, target-stat attestations,
  displace-then-replace update order, and last-applied directory metadata.
- `SCANNER.md`, `INVENTORY.md`, `DATABASE.md`, and `RECORDER.md`: stable
  `VolumeId`, corroborating volume evidence, typed unsupported/directory records,
  metadata snapshots, namespaced annotations, conditional target attestations,
  and filesystem/recording two-axis truth.
- `VERIFIER.md` and `HISTORY.md`: typed `IntegrityOutcome`, admission-time audit
  subscription, bounded backpressure, best-effort history durability, and loud
  degradation.
- `COMMANDLINE.md`, `INTERFACES.md`, `DESKTOP_UI.md`, and `INGEST.md`: exact
  commitment gate, corrected no-subcommand behavior, queue-only replay of
  commitments, folder-rename presentation grouping, and ingest provenance
  namespace/version snapshots.

All obsolete “DR-x must decide” placeholders were removed. The remaining open
language in module docs is deliberate and corresponds to the review blockers
below.

## Review Blockers Found

All seven blockers below were resolved on 2026-07-18: decision records live in
`DESIGN_REVIEW.md` as DR-25 through DR-31, and `FEATURES.md`/`ARCHITECTURE.md`
are updated to match. The original statements are retained for context.

1. **Executor/preflight layering contradiction.** Architecture says workflows
   are the only place modules meet and executor imports core only, but also says
   executor itself calls the preflight module unconditionally. The executor
   signature has no core guard protocol/callable. Choose workflow-owned
   observe/preflight under execution custody, or add an injected core guard
   protocol; direct executor-to-preflight import violates the import law.

2. **Non-hardlink update fallback is under-specified.** `CapabilityProfile` has
   no hardlink-support field, and the shared capacity formula does not explicitly
   count both the new replacement temp and the old-target backup copy. The copy
   backup also needs its own temp/flush/atomic-publish sequence before live
   replacement. Non-hardlink updates can otherwise pass preflight and predictably
   fail ENOSPC or retain a partial trash version.

3. **ADS/ACL preservation cannot be implemented from `MetadataSnapshot`.** The
   snapshot contains only ADS presence, not a stream manifest/content evidence,
   and no ACL snapshot. Source drift for named streams is therefore unguarded.
   Treating requested ADS-copy failure on an ADS-capable volume as only a warning
   can publish a result with silent user-data loss. Define the snapshot/copy/
   failure contract before claiming preservation.

4. **Directory metadata has no input for non-empty directories.** Scanner and
   Features retain `DirRecord` only for empty directories, while Executor
   promises source attributes/timestamps for every created directory. A newly
   created non-empty directory has no reviewed metadata snapshot. Either record
   every directory now or narrow the preservation promise.

5. **History degradation has no result field, and stalled-writer behavior is
   contradictory.** `OperationResult` exposes only ledger `RecordingStatus`,
   yet history failure must also surface on the session result. Separately,
   bounded memory plus guaranteed audit delivery requires waiting forever for a
   writer that stalls without failing, while the spec says history never blocks
   filesystem work. Add an audit status and an explicit timeout/degradation or
   durable-spill rule.

6. **Pause/cancel result transport is incomplete.** Bare `Canceled` and
   `PauseRequested` exceptions carry neither partial typed results nor a
   continuation. `ExecutionSet.status` covers execution resume, but no
   restart/continuation or duplicate-outcome rule exists for scan, baseline,
   verify, or import. The runner also says unexpected exceptions still surface
   after it emits terminal without defining how callers avoid a second terminal.

7. **Queued-discard audit lacks a typed generic distinction.** Dispatcher must
   remain domain-blind and history must not parse strings, but the current core
   state/event/result vocabulary cannot distinguish discarded-before-start from
   an ordinary zero-work cancellation. Add a generic typed terminal reason or
   attempt disposition before implementing Queue Discard Audit.

## Verification

- `git diff --check` passes.
- Focused docs contain no remaining obsolete `DR-xx`, `run_unattended_sync`,
  `target_free_space`, or `WAITING_INPUT` contract language.
- No runtime tests were run; this session changed documentation only.

## Next Work

The seven blockers are resolved in `FEATURES.md`/`ARCHITECTURE.md` with
decision records in `DESIGN_REVIEW.md` (DR-25 through DR-31). Remaining: remove
the matching explicit blocker notes from the module docs and propagate the new
contract details — workflow-owned preflight with executor per-op guards,
`supports_hardlinks` and profile-aware capacity, ADS stream manifests and
FAILED semantics, all-directory records with explicit mkdir-with-metadata, the
`audit` result axis and timeout-guarded backpressure, runner-assembled partial
results with per-kind pause capability, and the `Disposition` field. After
that, M0 can start with the core result/session/event shapes and import-law
tests without knowingly freezing contradictory bones.
