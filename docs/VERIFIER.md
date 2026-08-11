# Verifier Module

Status: the verifier component package and M1 Stage 3 location-centric
inventory/baseline/verify/rebaseline workflows are implemented. M1 Stage 4
also feeds the same ledger-neutral classifier transient post-copy candidates
for optional in-session readback. The production dispatcher registry carries
all four headless kinds and receipt-aware history v5 commits standalone and
compound detail incrementally before terminal.
Stage 5 exposes standalone activities through the shared-service CLI with
explicit location/scope binding and guarded selected rebaseline; desktop
actions remain Stage 6.

## Purpose

The verifier reads selected present inventory files and evaluates current
content against retained evidence. It creates missing baselines, distinguishes
ordinary modification from metadata-stable mismatch, emits a reliable typed
outcome per file, and requests conditional persistence through `Recorder`.

It does not inventory locations, choose repair actions, mutate file content,
write SQL, reinterpret copy-stream hashes as readback verification, or require a
paired source/target mapping.

## Component Boundary

`namisync.modules.verifier` is the stable facade and exports only
`WindowsUnbufferedReader`, `baseline`, `rebaseline`, `verify`, and
`verify_post_copy`. `engine.py` owns the public operations, selection
classification, progress, cancellation, recording settlement, and outcome
construction. `native.py` owns Windows root-chain admission, unbuffered reads,
handle/volume work, and final-path-by-handle checks. Engine may import native;
native imports only core contracts and the standard library and never imports
engine. Tests patch the submodule that owns each collaborator; direct reader,
handle, and cache-honesty cases live in `test_verifier_native.py`, separately
from the engine policy tests in `test_verifier_engine.py`.

## Entry Contracts

```python
baseline(selection, ctx, recorder, reader=None) -> IntegrityRunResult
verify(selection, ctx, recorder, reader=None) -> IntegrityRunResult
rebaseline(selection, ctx, recorder, reader=None) -> IntegrityRunResult
verify_post_copy(selection, ctx, recorder, reader=None) -> IntegrityRunResult
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
   changed, emit `modified` without calling it bitrot. A baseline-backed
   missing or modified result conditionally retains a metadata-drift
   invalidation.
5. Read through the cache-honest strategy while hashing XXH3-128 and reporting
   monotonic progress throttled by an injected monotonic clock. Construction,
   update, digest finalization, and raw-width validation use the same core
   evidence lifecycle as executor pipeline hashing.
6. Stat the same open subject/handle after reading; proven drift yields
   `modified` and conditionally records metadata-drift when baseline evidence
   exists. A generic read/stat error remains `error` and writes nothing.
7. If no stored hash, emit `baselined` and conditionally record a
   `VERIFY_ATTESTED` baseline.
8. If stats are stable and digest matches, emit `verified` and conditionally
   advance verification evidence.
9. If stats are stable and digest differs, emit `mismatched`; preserve the old
   baseline, conditionally retain a hash-mismatch invalidation, and never
   auto-accept.

Selection roots and display paths remain ordinary absolute drive/UNC spellings.
The Windows reader lexically normalizes the root without following links,
no-follow rejects a reparse in the configured root path below its trusted native
volume mount before Windows API setup, and then checks the selected child's path
components through extended-length native paths. It applies the
same conversion to volume and handle opens. No native prefix is persisted in
inventory or integrity evidence. A reviewed integrity or post-copy run carries
one ephemeral `RootAuthority`: the exact reviewed logical root, optional
reviewed mount anchor, and optional expected `VolumeId`. Every selected item,
including retained missing/unsupported rows and already-baselined shortcuts,
must name that exact logical root before reader or recorder work. Every readable
subject then freshly admits the authority before open; the check is evidence at
that point, not cached authorization. The native reader receives that authority
at construction or at the exact engine/native open boundary, then performs its
distinct chain-only final-touch check without another volume probe. Its
root-relative no-follow walk retains raw missing/access behavior while using
the shared reparse/placeholder classifiers. The default native reader requires
bound authority, while an unbound context remains only an explicit fake/custom-
reader test seam. Opened-handle volume identity and final-path-by-handle
containment remain independent checks; a stream without required corroboration
is unsupported rather than attestable.

Negative verification evidence is guarded by the same row/location/path/scope,
current-stat, baseline, and expected-invalidation facts as a positive write. A
stale/conflicting/error result degrades recording without rewriting the truthful
`missing`, `modified`, or `mismatched` verdict. Hash mismatch dominates later metadata
drift; matching scans cannot make it verified again. A successful verify or
explicit baseline/rebaseline evidence write atomically clears the marker.

Recorder calls are observations; a small pure reducer maps their typed
disposition or normalized error into reason, detail, recording status, and
record disposition. Item and post-copy positive writes and invalidations retain
four separate wrappers so they continue to build their distinct commands and
outcomes. `APPLIED` and `NOOP` preserve the truthful classification,
`STALE`/`CONFLICT` replace only the recording reason and discard subordinate
classification detail, and an ordinary recorder exception becomes
`RECORDING_ERROR`. A successful identityless post-copy read remains truthful
`verified` with degraded recording without entering this reducer because no
recorder call was possible.

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

The aligned native allocation is created once per opened file and freed when
that stream ends. Each yielded chunk is still materialized as a Python `bytes`
object for the current hasher protocol. That allocation is a performance seam,
not a correctness defect; change the stream/hasher lifetime contract only after
a profile shows chunk materialization is the limiting cost.

There is deliberately no buffered fallback. A non-Windows host, reparse
subject, alignment rejection, unsupported volume, or inability to prove handle
containment produces a disclosed `unsupported` outcome and never a false
`verified` result. Windows integration tests exercise an ordinary local file
through the actual unbuffered strategy.

## Baseline And Re-Baseline

Baseline writes only rows with no established hash and only if the row id,
present state, size, mtime, and identity still match. Encountering a null hash
during verify is `baselined`, never `verified`; because no comparison occurred,
its `phase=verify` result receives the `verification-incomplete` headline even
though an explicit baseline/rebaseline activity may complete successfully.

Re-baseline is an explicit user-reviewed acceptance of current modified content.
It uses the same fresh stat/hash/conditional write path, supplies the prior
attestation to the recorder for conflict detection/audit retention, and never
runs automatically after mismatch. A reappeared row receiving accepted
matching/new evidence clears `reappeared_at` atomically with that write.
Baseline/rebaseline replacement evidence never advances verification freshness
and clears a prior `last_verified_at`; only a true comparison match in verify
advances that timestamp. Copy/update/move-update evidence follows the same
freshness rule and replaces any prior invalidation only with new attested
evidence.

Workflow freezes a mode-aware initial selection before calling this module.
Baseline admits only eligible non-directory rows without an attestation;
rebaseline admits only rows with one; verify admits both. The filters are not
reapplied when a paused continuation already has exact candidate ids, so an
evidence change cannot remove admitted pending work. Repeating a full baseline
still refreshes and records inventory, but when every row already has evidence
it runs with zero verifier hashes and zero integrity-attestation writes.

## Selected And Post-Execution Verification

Selection lookup uses `rel_path_key`, never raw separators/case. Selected
verification refreshes only selected paths and does not pay for or infer missing
state across a full location. Post-execution verification contains only eligible
successfully executed operations; no-op or failed operations are not marked
verified merely because they appeared in the plan.

Standalone selections come from freshly refreshed role-free inventory. A
paused standalone session serializes the exact original candidate row ids plus
completed ids/bytes: resume inventories current physical state but cannot
silently add a newly appeared row or drop an admitted pending row.

Post-execution verification does not rebuild its immediate candidates from
ledger rows. The verifier's guarded open/stat/hash/classification body is
private and ledger-neutral; workflow feeds it transient published copy evidence
even when the copy-ledger write degraded. An optional complete recorded identity
only gates conditional advancement. Rowless candidates still open/stat/hash and
classify bytes; their integrity result stays truthful while recording remains
degraded. The verifier never fabricates row or location ids.

Manual verification is location-scoped and independent of any current plan or
mapping. It must not require both source and target roots.

Verify, baseline, and the implemented rebaseline entry point carry per-item
status as their pause continuation. They emit each reliable outcome before
advancing status; pause unwinds after preserving completed items, releases
custody without terminal, and resume freshly refreshes/guards only the remaining
selection. Rebaseline therefore uses the same continuation rather than a
separate short-operation exception.

`bytes_done` measures physical read work, not unique logical file coverage. A
pause during an in-flight file restarts that file on resume, so already-read
bytes are counted again while the item still emits exactly one terminal result;
the reporter expands its total as needed to keep progress monotonic and bounded.

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
- History incrementally commits every reliable preterminal item, including
  refusal and unexpected error, in bounded windows, then acknowledges terminal
  finalization before the runner releases `Terminal` to ordinary subscribers;
  history does not consume that terminal itself.
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
- package ownership and import direction enforced by AST and import-linter
  contracts while preserving the public facade.

Implemented by the Stage 3 composition around this module:

- automatic inventory creation and full/scoped refresh;
- exact-candidate pause continuation and fresh volume/root preflight;
- standalone integrity history-detail persistence and run finalization;
- dispatcher custody registration for inventory, baseline, verify, and
  rebaseline.

Implemented by the Stage 4 compound composition:

- post-copy candidates from successful eligible publishes only;
- matching readback despite copy-record failure, with no invented ledger ids;
- conditional stale recording as verified plus recording degradation;
- exact pause completion ids/bytes and no repeated outcomes on resume.

Implemented by the Stage 5 interface:

- explicit root or retained-location starts with exact repeatable selected
  paths and ambiguity mount choice;
- typed counts, per-item outcomes, phase summaries, and independent result axes;
- required selected scope plus explicit current-evidence intent for rebaseline.

Desktop actions remain a later M1 stage.

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
- Repeat baseline hashes/writes only missing evidence; rebaseline excludes
  missing-evidence rows; verify continues to baseline them and reports
  verification-incomplete.
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
