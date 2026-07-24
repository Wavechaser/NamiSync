# Verifier Module

Status: verifier operation module implemented during M0 construction; end-user
integrity workflow remains M1 because inventory selection, workflow/dispatcher
composition, history detail, and interfaces are separate dependencies.

The implemented slice is directly callable and testable through injected
reader, recorder, clock, event, and checkpoint contracts. It does not claim
that the location-centric integrity workflow is already surfaced to users.

## Purpose

The verifier reads selected present inventory files and evaluates current
content against retained evidence. It creates missing baselines, distinguishes
ordinary modification from metadata-stable mismatch, emits a reliable typed
outcome per file, and requests conditional persistence through `Recorder`.

It does not inventory locations, choose repair actions, mutate file content,
write SQL, reinterpret copy-stream hashes as readback verification, or require a
paired source/target mapping.

## Entry Contracts

```python
baseline(selection, ctx, recorder, reader=None) -> IntegrityRunResult
verify(selection, ctx, recorder, reader=None) -> IntegrityRunResult
rebaseline(selection, ctx, recorder, reader=None) -> IntegrityRunResult
```

Selections contain immutable inventory row id, location/root, canonical path
key, display path, expected current state/stat, retained `Attestation` (if any),
scope token, and reappearance state. `IntegritySelection` adds only the mutable
completed-item and processed-byte continuation needed for pause/resume. Workflow
must inventory or scoped-refresh before constructing selections; verifier never
silently inventories, changes mappings, or scans unselected paths.

Each file emits a reliable typed `IntegrityOutcome` carrying `IntegrityResult`:
`verified`, `baselined`, `mismatched`, `modified`, `missing`, `unsupported`,
`canceled`, or `error`. Generic `Outcome` remains the operation-level lifecycle
vocabulary and is not parsed to recover integrity meaning.

`IntegrityRunResult` is derived from emitted outcomes and carries the
independent aggregate recording axis. A conditional recorder refusal or error
degrades recording without rewriting a truthful content verdict.

## Per-File Algorithm

1. Checkpoint and validate root-relative path/containment.
2. Open the intended file without following an unexpected reparse point.
3. Stat before reading and compare size/mtime/identity with retained baseline.
4. If absent, emit `missing`; if unsupported, emit `unsupported`; if stat
   changed, emit `modified` without calling it bitrot.
5. Read through the cache-honest strategy while hashing SHA-256 and reporting
   monotonic progress throttled by an injected monotonic clock.
6. Stat the same open subject/handle after reading; drift yields `modified` or
   `error` and no write.
7. If no stored hash, emit `baselined` and conditionally record a
   `VERIFY_ATTESTED` baseline.
8. If stats are stable and digest matches, emit `verified` and conditionally
   advance verification evidence.
9. If stats are stable and digest differs, emit `mismatched`; preserve the old
   baseline and never auto-accept.

Every selected file emits exactly one reliable item result when the session
terminates, including cancel and error paths. Summary counts derive from those
results, not a separate mutable counter path. A pause is different: unreached
items remain pending and emit nothing until resume.

## Cache-Honest Reads

A verification match must attest storage, not merely pages populated by the
copy that just finished. `WindowsUnbufferedReader` opens the selected file with
`FILE_FLAG_NO_BUFFERING`, obtains the volume sector size, reads into
`VirtualAlloc`-aligned buffers in sector-multiple requests, and reports
`windows-unbuffered` in the item outcome. It rejects reparse components and
verifies that the opened handle's final path is exactly the selected path below
the resolved root. The handle permits other readers but denies writer/delete
sharing so the selected name cannot be replaced while it still refers to the
old subject. Pre- and post-read stats come from that same handle.

There is deliberately no buffered fallback. A non-Windows host, reparse
subject, alignment rejection, unsupported volume, or inability to prove handle
containment produces a disclosed `unsupported` outcome and never a false
`verified` result. Windows integration tests exercise an ordinary local file
through the actual unbuffered strategy.

## Baseline And Re-Baseline

Baseline writes only rows with no established hash and only if the row id,
present state, size, mtime, and identity still match. Encountering a null hash
during verify is `baselined`, never `verified`.

Re-baseline is an explicit user-reviewed acceptance of current modified content.
It uses the same fresh stat/hash/conditional write path, supplies the prior
attestation to the recorder for conflict detection/audit retention, and never
runs automatically after mismatch. A reappeared row receiving accepted
matching/new evidence clears `reappeared_at` atomically with that write.

## Selected And Linked Verification

Selection lookup uses `rel_path_key`, never raw separators/case. Selected
verification refreshes only selected paths and does not pay for or infer missing
state across a full location. Post-execution verification contains only eligible
successfully executed operations; no-op or failed operations are not marked
verified merely because they appeared in the plan.

The linked selection is built ledger-first: the workflow reads back the
inventory rows execution just recorded (through read-only repositories, keyed by
the eligible executed operations' canonical target paths) rather than receiving
row identities from the executor, which stays domain-blind and surfaces only
op-level outcomes. A pure move preserves the moved row's existing hash and
attestation, so verifying a moved file verifies against carried-forward evidence
rather than re-baselining; a moved file that never had a hash baselines on first
verify.

Manual verification is location-scoped and independent of any current plan or
mapping. It must not require both source and target roots.

Verify, baseline, and the implemented rebaseline entry point carry per-item
status as their pause continuation. They emit each reliable outcome before
advancing status; pause unwinds after preserving completed items, releases
custody without terminal, and resume freshly refreshes/guards only the remaining
selection. Rebaseline therefore uses the same continuation rather than a
separate short-operation exception.

On cancellation, the verifier's unwind finalizer emits `canceled` for the
in-flight file and every unreached selected file before re-raising `Canceled` to
the runner. On pause, that finalizer emits nothing for them. This makes runner
aggregation lossless without exposing verifier internals or duplicating results
after resume.

## Expectations Of Other Modules

- Core supplies `IntegrityOutcome`, integrity/result/event evidence types, and
  the one generic session runner.
- Inventory workflow/repositories supply freshly refreshed canonical selections;
  verifier does not infer inventory or mappings.
- Recorder owns every evidence write and enforces the conditional primitive.
- `COPY_ATTESTED` may provide a baseline digest but never advances
  `last_verified_at`; only an honest verifier read does.
- Dispatcher/session runner supplies custody, checkpoint, and one terminal.
- History observes every preterminal item, including refusal and unexpected
  error, then acknowledges finalization before the runner releases `Terminal`
  to ordinary subscribers; history does not consume that terminal itself.
- UI consumes typed results and updates inventory rows, not plan rows by loose
  path matching.
- Ledger `recording` and history `audit` degradation are surfaced independently
  from each other and from content verdicts.

## Latent Features

Worker-count policy may add per-volume multithreading after benchmarks. Results
remain deterministic and each row retains one conditional write. HDD paths may
pipeline IO/CPU without random-seek explosion. Background integrity is an
ordinary dispatcher session. Repair guidance compares both sides against
retained evidence but generates a new plan; verifier never restores content.

## Implementation Boundary

Implemented and directly verified in this module:

- the complete stat-first/digest-second classification matrix;
- null-hash verify, baseline, explicit rebaseline, provenance, and one
  conditional recorder command per eligible row;
- canonical path/location guards and selection-only access;
- one reliable typed result per settled row, including read/error and complete
  cancel unwind;
- outcome-before-continuation pause/resume behavior;
- monotonic throttled progress, including retried work after pause;
- the real Windows unbuffered reader and disclosed unsupported path;
- sibling-free imports (`namisync.modules.verifier` imports `core` only).

Still owned by the M1 composition around this module:

- automatic inventory creation and full/scoped refresh;
- constructing post-execution selections from successful eligible operations;
- integrity workflow/history-detail persistence and run finalization;
- dispatcher custody registration and interface presentation.

The shared SQLite ledger already implements the injected conditional
`record_integrity` command, including atomic evidence/reappearance updates and
rollback on write failure; the integration test exercises that real boundary.

Those seams are explicit injected contracts, not placeholder calls or sibling
imports inside the verifier.

## PoC Hardening

- Stat-first classification separates modified from metadata-stable mismatch.
- Canonical key lookup fixes scoped casing/separator failures.
- Baseline write clears stale reappearance state in the same transaction.
- Explicit rebaseline closes the permanent-modified workflow gap.
- Conditional writes prevent hashes attaching to stale metadata.
- Bounded recording avoids a multi-hour all-or-nothing write transaction.
- Inventory-before-verify and scoped refresh fix no-inventory failures and
  100k-file selected-verify full walks.
- Result scope prevents the GUI from marking whole directories/noops verified.

## Acceptance Criteria

- Stat-changed content is `modified`; only stat-stable digest divergence is
  `mismatched` across a full classification matrix.
- Null-hash verify is `baselined`, stores verify provenance, and does not claim a
  prior verification match.
- Copy-stream-only evidence never sets or renders `last_verified_at`.
- Missing, unsupported, canceled, and read/error paths each emit one item result
  and no unsafe write.
- Drift between pre-stat, hash, post-stat, and recorder call causes the
  conditional write to affect zero rows.
- Reappeared first-baseline clears `reappeared_at` atomically; rollback leaves
  both old states intact.
- Selected casing/separator variants resolve by canonical key and never target a
  row from another location.
- Selected refresh observes only selected paths and cannot mark others missing.
- Post-execution scope includes only successful eligible operation ids; manual
  verify cannot mark plan noops executed/verified.
- Cache-honest integration tests prove the declared Windows read strategy or
  produce a disclosed unsupported/deferred outcome.
- Progress emission is throttled under fast-disk simulation and remains
  monotonic; a chunk flood cannot drive full-widget updates per MiB.
- Verification remains single-stream with no worker-count setting. Any future
  parallel verifier design requires workload evidence and must preserve one
  outcome/write per row plus per-volume safety.
- Unexpected SQLite/OS errors still produce an audited activity envelope and a
  truthful terminal.
- Pause after any item count preserves exactly those outcomes/writes, releases
  custody with no terminal, and resume neither repeats outcomes nor skips an
  unreached selected row.
- Cancellation after any item count emits exactly one result for every selected
  row, including in-flight and unreached canceled rows, before runner unwind.
- Import-linter proves verifier imports core but no sibling module.
