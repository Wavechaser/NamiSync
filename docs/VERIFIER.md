# Verifier Module

Status: the verifier component package and M1 Stage 3 location-centric
inventory/baseline/verify/rebaseline workflows are implemented. M1 Stage 4
also feeds the same ledger-neutral classifier transient post-copy candidates
for optional in-session readback. The production dispatcher registry carries
all four headless kinds and receipt-aware history v6 commits standalone and
compound detail incrementally before terminal.
Stage 5 exposes standalone activities through the shared-service CLI with
explicit location/scope binding and guarded selected rebaseline; desktop
actions remain Stage 6. Signed-64 totals, exact event v5, and full-width native
identity are active from checkpoint 3.2. The no-rescan manual post-copy handoff
and ledger-current classification below remain accepted Stage 6 targets until
their implementation gates close.
Checkpoint 10 also broadens fresh rebaseline admission to rows without prior
evidence; that selection change is accepted but not yet implemented.

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
construction, including selected-root and opened-handle volume policy.
`native.py` owns Windows root-chain admission, unbuffered reads, handle work,
and final-path-by-handle checks. Engine may import native;
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
scope token, and reappearance state. `IntegritySelection` adds the mutable
completed-item state, processed-byte high-water, and nondecreasing admitted
physical-read budget needed for pause/resume. Workflow
must inventory or scoped-refresh before constructing selections; verifier never
silently inventories, changes mappings, or scans unselected paths.

Each file emits a reliable typed `IntegrityOutcome` carrying `IntegrityResult`:
`verified`, `baselined`, `mismatched`, `modified`, `missing`, `unsupported`,
`canceled`, or `error`. Generic `Outcome` remains the operation-level lifecycle
vocabulary and is not parsed to recover integrity meaning.

`IntegrityRunResult` is derived from emitted outcomes and carries the
independent aggregate recording axis. A conditional recorder refusal or error
degrades recording without rewriting a truthful content verdict.

Verification remains single-stream with no worker-count setting. Any future
parallel verifier design requires workload evidence and must preserve one
outcome/write per row plus per-volume safety.

## Per-File Algorithm

The old-baseline stat and digest comparisons below apply to **verify**.
Baseline and rebaseline use the same fresh-subject/read-stability guards but
their mode-specific evidence policy is defined under
[Baseline And Re-Baseline](#baseline-and-re-baseline).

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
that point, not cached authorization. Core exposes a runtime-checkable
`AuthorityBoundVerificationReader` seam. Engine dispatches that seam
structurally, so native subclasses and decorators cannot silently fall back to
the unbound `open(root, path)` route; any authority-bound reader in an unbound
context is refused. The bound open receives only the relative path and authority
and derives its native root from `authority.logical_root`, so it cannot validate
one root and open another. The native reader then performs its distinct
chain-only final-touch check without another volume probe. Its
root-relative no-follow walk retains raw missing/access behavior while using
the shared reparse/placeholder classifiers. The default native reader requires
bound authority, while an unbound context remains only an explicit fake/custom-
reader test seam. Engine checks opened-handle volume identity from the stream's
first stat; native final-path-by-handle containment remains independent. A
stream without required corroboration is unsupported rather than attestable.

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
object for the current hasher protocol. `VerifierContext.chunk_size` is an
exact integer from 1 through 4,194,304 bytes; the default and public maximum are
both 4 MiB. One open Windows stream therefore owns at most one 4 MiB aligned
native buffer and one 4 MiB Python chunk at the same time. Smaller configured
chunks remain supported. Change the stream/hasher lifetime contract only after
a profile shows chunk materialization is the limiting cost.

`IntegrityRecordCommand` and `VerifierContext` are frozen and slotted. Their
declared fields, validation, recorder semantics, continuation policy, and
factory binding remain unchanged. Named internal (rung 3) transfers validate
exact type and declared fields once, after which first-party readers trust the
immutable values. External (rung 1) filesystem observations and reentrant
(rung 2) callbacks retain their separate admission and ordering policy.

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

Re-baseline is explicit user-reviewed acceptance of current content, whether
or not that content differs from prior evidence.
It uses the same fresh stat/hash/conditional write path, supplies the prior
attestation to the recorder for conditional conflict detection, and never
runs automatically after mismatch. A reappeared row receiving accepted
matching/new evidence clears `reappeared_at` atomically with that write.
Baseline/rebaseline replacement evidence never advances verification freshness
and clears a prior `last_verified_at`; only a true comparison match in verify
advances that timestamp. Copy/update/move-update evidence follows the same
freshness rule and replaces any prior invalidation only with new attested
evidence.

The current workflow freezes a mode-aware initial selection before calling this module.
Baseline admits only eligible non-directory rows without an attestation;
rebaseline admits only rows with one; verify admits both. The filters are not
reapplied when a paused continuation already has exact candidate ids, so an
evidence change cannot remove admitted pending work. Repeating a full baseline
still refreshes and records inventory, but when every row already has evidence
it runs with zero verifier hashes and zero integrity-attestation writes.

### Standalone operation policy (checkpoint 10 target)

This table governs the accepted checkpoint-10 behavior after fresh inventory,
for eligible readable files whose current subject remains stable during the
read. Only rebaseline's missing-evidence admission changes; all other cells
describe existing policy. Until checkpoint 10 lands, fresh rebaseline still
excludes rows without evidence as stated above.

| Operation | No prior evidence | Prior evidence exists | Successful evidence / verification freshness |
| --- | --- | --- | --- |
| Baseline | Hash and conditionally create a baseline. | Not admitted to verifier work; no verifier hash or attestation write. | Report `baselined`; do not claim a comparison or advance `last_verified_at`. |
| Verify | Hash and conditionally create a baseline; report `baselined`, so the verify phase is `verification-incomplete`. | Changed baseline stat: `modified` without hashing. Stable stat: hash; equal digest is `verified`, different digest is `mismatched` and never auto-accepted. | Only a genuine comparison match advances `last_verified_at`; negative results retain prior evidence and may conditionally record invalidation. |
| Rebaseline | **New at checkpoint 10:** hash and conditionally create a baseline, accepting null as the prior evidence state. | Hash and conditionally replace with fresh evidence, including when the digest genuinely matches. | Report `baselined`, never `verified`; clear prior `last_verified_at`, leaving the successfully baselined row `unverified`. |

These are workflow admission rules, not silent per-item `skipped` results.
Fresh inventory may still update observations for excluded baseline subjects.
Rebaseline keeps its explicit selected scope and current-evidence acceptance,
including an all-null selection. An unchanged digest does not bypass the read,
convert the mode to verify, preserve verification freshness, or avoid the fresh
evidence write. Compare-and-accept treatment of genuine rebaseline matches is
deferred beyond M1. Exact command/receipt replay may still be an idempotent
`NOOP`; it is not that deferred content-match behavior.

All modes keep fresh root/volume, current-stat, complete-read, and same-subject
post-read guards. Missing, unsupported, canceled, drift, and error outcomes
remain truthful; a failed read cannot install replacement positive evidence.
Applicable negative invalidations retain their existing conditional-write rule.
Every positive write guards prior evidence **including its absence**, so a
concurrent null-to-present evidence change refuses instead of overwriting the
new evidence. Recorder refusal/error degrades recording without rewriting the
content verdict. Successful replacement clears invalidation/reappearance only
atomically with the evidence transaction. Pause/resume retains exact admitted
ids/order and completed results without reapplying fresh-selection filters.
Automatic linked and manual exact post-copy verification remain separate.
Delivery and regression gates live in [H2 checkpoint 10](M1_SHELL_H2.md#10-deliver-integrity-and-deferred-post-copy-verification).

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

The workflow also supplies the complete post-copy phase admission separately
from the readable candidate selection. A successful operation whose publication
evidence is missing therefore remains visible in every verify `Progress`
`items_total` and `bytes_total` even though no `PostCopyCandidate` can be built
for it; the same admission feeds the incomplete terminal phase. This paired
invocation context is not continuation state and does not alter the plan
payload's exact version 5: resume re-derives it from the exact
`VerifyContinuation` before constructing the reporter. Exact continuation and
event versions, closed detail projection, scalar domains, omission witnesses,
and envelope limits are owned by
[M1_BRIDGE.md](M1_BRIDGE.md); verifier preserves only the local pause/resume
state needed to continue the same admitted work. The enclosing sync-execution
payload is exact v7.

Ordinary manual verification is location-scoped and independent of any current
plan or mapping. It must not require both source and target roots. The deferred
post-copy action is a separate, explicitly execution-linked workflow.

### Accepted Stage 6 manual post-copy handoff (not active)

Deferred exact verification classifies current durable ledger state; it never
reconstructs candidates from retained operation-time hashes. Those transient
attestations exist only for immediate linked verification and same-session
pause/resume and never become history, ledger, task, or JavaScript state. The
exact atomic join and presentation classification are centralized in
[M1_BRIDGE.md](M1_BRIDGE.md) and [DATABASE.md](DATABASE.md).

A handoff is ready only when every applicable selected byte-producing operation
has a successful terminal outcome and current committed evidence. An unrelated
non-byte failure or a task-level close/flush issue does not erase committed
evidence, but unrecorded, superseded, incomplete, or post-settlement-diverged
work blocks the exact handoff. An empty applicable set is not vacuous success,
and an all-already-verified set starts no work.

Start never treats a prior read as authorization. It reclassifies atomically,
freshly admits the target only for a ready subset, then classifies once more to
freeze the work. The verifier reads and conditionally records against the
original execution scope; a last-moment row, stat, scope, mount, or invalidation
race becomes a truthful item/result disposition rather than evidence for a
different state.

A ready handoff receives a new dispatcher/history session and publishes only
the task's replaceable post-copy result. It cannot rewrite immutable execution
truth or the ordinary-integrity result. A later attempt may retry only what is
currently ready. When exact handoff is unavailable, the fallback is an
explicitly ordinary verify-current workflow whose refresh may establish a new
scope. Exact replacement retention and task attachment semantics remain bridge
authority.

At the active checkpoint-3.2 scalar cutover, verifier totals follow the checked-arithmetic
contract in [M1_BRIDGE.md](M1_BRIDGE.md) and [DEFENSE.md](DEFENSE.md) §1.3;
verifier defines no local numeric or file-identity variant.

Verify, baseline, and the implemented rebaseline entry point carry per-item
status as their pause continuation. They emit each reliable outcome before
advancing status; pause unwinds after preserving completed items, releases
custody without terminal, and resume freshly refreshes/guards only the remaining
selection. Rebaseline therefore uses the same continuation rather than a
separate short-operation exception.

Once the standalone workflow has frozen that selection, running cancellation
and unexpected failure build terminal byte truth from the live selection's
physical-read high-water and admitted item sizes, never from whichever lossy
Progress happened to reach the session runner. `PauseRequested` remains a
control signal and is not normalized into a terminal result. Cancellation of a
paused baseline/verify/rebaseline session instead uses the exact stored v2
continuation without reopening an invocation, rescanning, or hashing. Version 2
persists `processed_bytes`, the nondecreasing physical-read
`bytes_total_high_water`, and the one-way aggregate `recording` status. Paused
cancellation and failures before selection reconstruction therefore retain the
attempted-work budget and degradation already earned before pause. These byte
counters describe attempted physical read work, not durable publication;
reliable outcomes and recorded evidence remain the authority for item and
durability truth. Version 1 is refused rather than migrated because this
payload remains process-local paused custody and is never persisted as a
restart-stable workflow artifact.

A degraded reliable outcome or recorder-close failure advances aggregate
recording to `DEGRADED` before a paused snapshot is serialized, and later resume
cannot recover it to `OK`. During one live invocation, ledger owner close
failure cannot replace an in-flight pause, cancellation, or verifier exception;
it degrades recording where a terminal result exists, and a lone close failure
becomes a selection-derived failure with authoritative bytes.

The shared version-5 field meanings, transition authority, and recovery rules
are owned centrally by `ARCHITECTURE.md` §2.3. The following paragraphs record
only the verifier's implementation of that protocol.

`bytes_done` measures physical read work, not unique logical file coverage. A
pause during an in-flight file restarts that file on resume, so already-read
bytes are counted again while the item still emits exactly one terminal result;
the aggregate total expands as needed to keep that physical-work progress
monotonic and bounded.

Verifier Progress self-describes its active mode as `phase=verify`,
`phase=baseline`, or `phase=rebaseline`. Each pending standalone row first
emits its stable item id with `item_type=integrity`; a post-copy candidate keyed
by its originating executor operation id uses `item_type=operation`. The type
names the UI row-lookup namespace, not the verifier phase or the reliable
outcome kind, so post-copy settlement remains an `IntegrityOutcome`. Identity
begins with no attempt id or byte counters. Only after the opened handle has
passed volume, expected-stat, and baseline-subject guards does the reporter
mint a fresh opaque 32-lowercase-hex attempt id and start a determinate stream
at `0 / opened_size`. Chunk callbacks advance that attempt-local counter. If a
changing subject yields more bytes than that admitted size, later snapshots
keep item and attempt identity active but omit both item-byte counters rather
than expanding the item admission; the aggregate total still expands to count
all physical work.
A reliable `IntegrityOutcome` precedes completion bookkeeping and a
normally throttled inactive transition that clears all item fields while
retaining the last display path. Item start, determinate-stream start, and item
completion use the same ordinary throttle path. A successful verifier phase
force-emits only its initial and final inactive boundary snapshots, independent
of selected-item count. The reporter counts an item immediately after its
reliable outcome emission succeeds, before mutable continuation bookkeeping;
therefore a later continuation failure cannot make `items_done` contradict an
outcome already released to consumers, while a failed outcome emission does
not advance the count.

Pause does not invent a settlement state: after the read unwinds it force-emits
the latest active attempt when a stream is in flight, so the 100 ms throttle
cannot leave a stale paused byte count; a pause at an inter-item checkpoint is
truthfully inactive. Resume re-entry mints a new attempt id whose item counter
starts at zero while the aggregate physical-read counter retains prior work and
never regresses. When a pause, cancellation, or exceptional unwind abandons a
partially consumed attempt, the reporter expands its physical-read budget by
the consumed admitted portion before the forced control snapshot; a resumed
invocation therefore begins from the same continuation-derived budget rather
than revealing a later jump. Cancellation emits every
required canceled outcome before one forced inactive control snapshot. Pause
likewise adds one forced control snapshot, active only when an attempt is in
flight; neither path emits the successful-phase final boundary. Ordinary
lifecycle and chunk updates remain time-throttled and lossy-coalescible.

An unexpected verifier exception, including reader construction or an
in-flight byte-pipeline failure, clears item, attempt, item-byte, and path state
and force-emits one inactive snapshot from the live outcome count and physical
read high-water before the original exception escapes. If that secondary
Progress emission also fails, its diagnostic is attached to the original
exception; it never replaces the primary failure. Reporter construction and
its phase-entry snapshot precede reader resolution, so a resumed continuation
does not fall back to zero merely because reader setup fails.

On cancellation, the verifier's unwind finalizer emits `canceled` for the
in-flight file and every unreached selected file before re-raising `Canceled` to
the runner. On pause, that finalizer emits nothing for them. This makes runner
aggregation lossless without exposing verifier internals or duplicating results
after resume. If canceled-outcome emission or its continuation bookkeeping
fails, the settlement error replaces the control unwind, passes through the
same forced inactive failure boundary, and remains primary if that Progress
sink also fails.

Progress emission is throttled under fast-disk simulation and aggregate
physical-read work remains monotonic. The frozen-clock source fixture set
covers 20 standalone streamed and 20 nonstreamed items
(`test_fast_items_have_constant_progress_boundaries`), 20 streamed post-copy
candidates (`test_fast_post_copy_items_have_constant_progress_boundaries`),
empty standalone and post-copy selections
(`test_empty_successful_selection_has_two_inactive_progress_boundaries`), and
one 100-byte item delivered as 100 one-byte chunks
(`test_fast_chunk_flood_has_two_fixed_progress_boundaries`). Every successful
profile passes exactly two forced `Progress` snapshots to the injected
emitter: the initial and final inactive phase boundaries.
Item/stream/settlement transitions use the ordinary throttle path; a pause or
cancellation adds exactly one forced control-boundary snapshot instead of a
successful final boundary. Downstream progress remains lossy and coalescible,
so this fixed source-emission cost is not a promise of two browser callbacks.
This is a deterministic source-enforced lifecycle invariant, not an empirical
latency SLO: item and chunk counts are scaling axes only for ordinary
throttle attempts, no measurement artifact is retained, and the set reruns
whenever reporter force sites, the 100 ms throttle, or phase-boundary handling
changes.

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

Desktop actions remain a later M1 stage. The contracts above define their
accepted target without claiming implementation.

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
