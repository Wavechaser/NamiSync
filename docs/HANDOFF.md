# NamiSync Session Handoff

Date: 2026-07-24

## Session Outcome

M1 Stages 2 and 3 are implemented and integrated on `milestone1`. Stage 2
delivers the adaptive single-file executor pipeline, native finalization
reductions, fixed XXH3-128 content evidence, and the final reset-only storage
contract. The parallel Stage 3 work delivers role-free inventory and
production-composed standalone baseline/verify/rebaseline workflows without
premature CLI/UI commands or Stage 4 compound types.

No user database was deleted. Pre-switch development databases must be reset as
one coordinated pair before running this tip, even if they already report
ledger v2/history v3. Initialization refuses nonempty transitional, missing-
marker, mismatched-marker, old, or unversioned databases before writer/schema
work; only a genuinely fresh absent/empty file may create the final schema.
Read repositories additionally refuse an empty existing database, and every
refusal preserves its main file and SQLite sidecars.

The frozen schema decision is `M1-SCHEMA-CONTRACT-20260724-02`:

- metadata key: `contract_id`
- ledger: `m1-ledger-xxh3-128-mapping-filters-v1`
- history: `m1-history-generic-items-phases-v1`

## Changes

### Stage 2 — Executor And Content Evidence

- Replaced the serial copy loop with one immutable
  caller/reader → hasher → writer pipeline per file. It uses one combined
  32 MiB payload budget, 32-item caps on both FIFOs, deterministic first-error
  teardown, and no cross-file concurrency.
- Fixed copy chunks at 256 KiB below 8 MiB, 1 MiB below 32 MiB, and 4 MiB
  thereafter, capped only by the existing private policy ceiling. Every size,
  including empty and 4 KiB files, uses the same pipeline.
- Added cached `O_SEQUENTIAL` source opens, process-lifetime Win32 bindings,
  exact exclusive temp creation, and conditional `FileAllocationInfo`
  preallocation at 8 MiB. Only WinErrors 1/50/120 fall back; disk-full, quota,
  permission, and unknown allocation failures stop before streaming.
- Consolidated temp metadata and durability into one handle acquired before ACL
  application: normalized basic information, exactly one real
  `FlushFileBuffers`, then close. Publication performs one comparison stat and
  repairs/flushes only fields actually changed by publication.
- Preserved the serial, hashless, fixed-4-MiB, unallocated copied-backup loop.
  Added published-size guards for copy/update/move-update and exact
  never-neither fault coverage for every composite move-update stage.
- Atomically switched `CopyDigest`, `ContentEvidence`, executor, verifier,
  repositories, fixtures, and test setup to raw 16-byte `xxh3_128`. The sole
  concrete import is `workflows/runtime.py`, which retains one exact
  `xxhash.xxh3_128` object for both consumers; executor and verifier retain
  different opener strategies.
- Extracted verifier byte guarding/hashing/classification into the private
  ledger-neutral `_classify_subject`. Standalone inventory/path-policy checks
  and conditional ledger recording remain in the outer adapter. This is the
  reusable Stage 4 body; no `PostCopyCandidate` or other compound public seam
  was added.
- Made repository opens validate version then exact contract marker through
  their existing read-only connection before exposure, closing that connection
  on refusal. Coordinated reset also removes rollback-journal artifacts.
- Fixed verification freshness: copy/update/move-update evidence always clears
  `last_verified_at`; baseline/rebaseline and verify-without-baseline do not
  advance it; an actual verified read does.

### Stage 3 — Inventory And Standalone Integrity

- Added workflow-owned five-state volume/root resolution: resolved, offline,
  ambiguous, root-missing, and root-unavailable. First registration remains
  host → volume → role-free location → scan → inventory record and never
  creates a mapping.
- Corrected selected-scan completeness at the scanner producer and added exact
  full/selected reconciliation. Dynamic current `FilterSet` controls mapping
  eligibility; mapping exclusions are snapshot-tagged cache/audit projections,
  never physical presence or an independent authority.
- Added immutable typed inventory/filter/location repository snapshots,
  acknowledge/restore and staleness reads, two-mapping isolation, and atomic
  full-coverage filter replacement.
- Replaced operation-only result assumptions with nominal ordered
  `ResultItem`s. `OperationResult.items`, reliable event accumulation, generic
  history v3 items, integrity phase tags, and workflow views now share that
  contract. Standalone Stage 3 writes zero `history_phases` rows.
- Production runtime now prepares/opens inventory, baseline, verify, and
  rebaseline, registers their latent dispatcher workflows with correct pause
  flags, and persists subject-scoped history. The parser still exposes only
  sync and history commands.
- Integrity start, queued wakeup, and resume re-resolve the recorded volume and
  root before scan/hash. Continuation freezes the exact admitted item ids plus
  cumulative progress/completions; newly inventoried rows are not silently
  admitted on resume.
- Corrected integrity headline precedence, continuation validation, and Windows
  extended-length root probing during the final adversarial pass.

## Benchmarks

The required five corpora ran from `F:` (WD Black SN850X 1) to separate
`G:` NAND, `E:` Optane, and `J:` HDD targets. Final current-tip results,
controlled retired-serial comparisons, fixed finalization time, stage waits,
payload high-water, and the three-repeat allocation sweep are recorded in
`HASH_REFACTOR.md` §2.8.

The final current executor reached:

- `G:` 412.182 ops/s for 1,000×4 KiB and 2,033.930 MiB/s for 1×4 GiB.
- `E:` 337.106 ops/s for 1,000×4 KiB and 1,074.493 MiB/s for 1×4 GiB.
- `J:` 50.177 ops/s for 1,000×4 KiB and 226.176 MiB/s for 1×4 GiB.

The controlled comparison improved small-file operations/s over the retired
serial SHA-256 executor by 83.1%, 92.1%, and 37.6% respectively. The retained
result files are external evidence, not repository artifacts:

- `G:\NamiSyncExecutorBenchTarget\stage2-benchmark-results-20260724T162902Z-7c926921a5f14f49b2687985a2c6159c.json`
- `E:\NamiSyncExecutorBenchTarget\stage2-benchmark-results-20260724T162933Z-dbc9487982914e198deea718eab5206e.json`
- `J:\NamiSyncExecutorBenchTarget\stage2-benchmark-results-20260724T163044Z-11bf11be96644373be9570e6498e957c.json`

The source corpora remain under `F:\NamiSyncExecutorBenchSource\` in
`1000x4KiB`, `512x128KiB`, `64x4MiB`, `4x128MiB`, and `1x4GiB`.

## Adversarial Review

Separate builder, contract-owner, Stage 3, and final reviewer passes checked
every `HASH_REFACTOR.md` A1–A16, B1–B20, and C1–C11 gate for a proof that would
fail if the named behavior were removed.

The review found and fixed substantive issues:

- copy/rebaseline evidence could preserve stale `last_verified_at`;
- read repositories bypassed the version/contract reset gate;
- verifier classification was coupled to ledger row/recorder identity;
- modified/missing and verify-phase null-baseline headlines could claim success;
- malformed continuation progress could omit the frozen selection;
- Windows root probing missed the extended-length path boundary;
- the real-ACL and process-exit tests observed a wrapper rather than the native
  flush binding, so a zero/wrong-handle mutation could pass; and
- factory identity and opener distinction were split across separate tests
  rather than one production-composition C5 proof.

The final proofs now delegate the real native flush and require the exact temp
handle lifecycle `open → basic-info → native-flush → close` before recording
and process exit. The C5 runtime test captures contexts passed to the actual
configured verifier runners and proves one object identity chain through
runtime, copy backend, verifier, and exact `xxh3_128` while also observing
`O_SEQUENTIAL` versus `WINDOWS_UNBUFFERED`.

No Stage 4 public type leaked, no workflow contains SQL, no executor/preflight
path reads settings or `worker_count`, core has no third-party import, and
SHA-256 remains restricted to plan/selection/custody/history/recorder identity.

## Verification

- Full integrated suite: `531 passed in 17.90s`.
- Executor/pipeline/native-ACL/verifier slice: `210 passed`.
- Final C5/B14/B15 anti-slack proof: `3 passed`; enclosing runtime/executor
  slice: `135 passed`.
- Recorder/schema/repository/history checkpoint: `66 passed`.
- Import/package contract tests: `5 passed`; Import Linter: all 7 contracts
  kept.
- `python -m compileall -q namisync`: clean.
- `git diff --check`: no whitespace errors; only expected LF-to-CRLF notices.
- Static checks: sole production `xxhash` import is `workflows/runtime.py`; no
  Stage 4 types, workflow SQL, hidden inventory/integrity parser commands,
  `worker_count`, or settings-dependent execution path.

## Immediate Next Context

1. Stage 4 may now add the planned execute→verify compound session and its
   public `PublishedCopyEvidence`, `PostCopyCandidate`, phase result, and
   continuation contracts. It must reuse `_classify_subject`, the exact runtime
   hasher object, and the distinct cache-honest verifier reader rather than
   reopening the hashing contract.
2. Successful copy/update/move-update publication must feed transient readback
   evidence even when ledger recording degraded. Filesystem, integrity,
   recording, and audit remain independent axes; a recorder failure is not a
   byte failure.
3. Preserve one session and one volume-custody interval across execute→verify.
   Pause continuation must retain phase and successful published evidence.
   Application-restart recovery remains M2.
4. Before any local run against prior development data, close all NamiSync
   processes and reset both configured database files together. Do not migrate,
   backfill a marker, accept mixed algorithms, or add another numeric schema
   bump.
5. `OperationResult.items` is authoritative. Session terminal publication
   replaces workflow-authored items with the ordered reliable event
   accumulation; do not restore `operations=` or parallel result lists.
6. Current dynamic mapping filters alone decide eligibility. Treat persisted
   exclusions as a snapshot-hash-tagged projection and surface staleness
   without making the projection authoritative.
7. File-level concurrency, direct/unbuffered executor IO, batching, and
   cross-file publish overlap remain deferred until new post-XXH3 production
   measurements justify their complexity.
8. Stage 5 may expose inventory/integrity through CLI/UI. Stage 3 intentionally
   registered the production workflows without adding parser commands.
