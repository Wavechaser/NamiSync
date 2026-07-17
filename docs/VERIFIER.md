# Verifier Module

Status: draft contract. Priority: M1 after inventory and conditional recorder
primitives exist.

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
baseline(selection, ctx, recorder, reader) -> IntegrityResult
verify(selection, ctx, recorder, reader) -> IntegrityResult
rebaseline(selection, ctx, recorder, reader) -> IntegrityResult
```

Selections contain immutable inventory row id, location/root, canonical path
key, display path, expected state/stat/hash/provenance, and scope token. Workflow
must inventory or scoped-refresh before constructing them; verifier never
silently operates on stale/missing inventory.

The generic event `Outcome` is insufficient for integrity meaning. DR-14 must
freeze a typed `IntegrityOutcome`: `verified`, `baselined`, `mismatched`,
`modified`, `missing`, `unsupported`, `canceled`, and `error`.

## Per-File Algorithm

1. Checkpoint and validate root-relative path/containment.
2. Open the intended file without following an unexpected reparse point.
3. Stat before reading and compare size/mtime/identity with retained baseline.
4. If absent, emit `missing`; if unsupported, emit `unsupported`; if stat
   changed, emit `modified` without calling it bitrot.
5. Read through the cache-honest strategy while hashing SHA-256 and reporting
   throttled progress.
6. Stat the same open subject/handle after reading; drift yields `modified` or
   `error` and no write.
7. If no stored hash, emit `baselined` and conditionally record a
   `VERIFY_ATTESTED` baseline.
8. If stats are stable and digest matches, emit `verified` and conditionally
   advance verification evidence.
9. If stats are stable and digest differs, emit `mismatched`; preserve the old
   baseline and never auto-accept.

Every selected file emits exactly one reliable item result even when canceled
or errored. Summary counts derive from those results, not a separate mutable
counter path.

## Cache-Honest Reads

A verification match must attest storage, not merely pages populated by the
copy that just finished. The Windows strategy must be selected and tested before
M1: unbuffered reads require alignment and filesystem support; a safe fallback
may defer post-copy verification beyond cache pressure. The outcome/provenance
must disclose which supported strategy actually ran. Unsupported honest-read
conditions are deferred/unsupported, not silently downgraded to verified.

## Baseline And Re-Baseline

Baseline writes only rows with no established hash and only if the row id,
present state, size, mtime, and identity still match. Encountering a null hash
during verify is `baselined`, never `verified`.

Re-baseline is an explicit user-reviewed acceptance of current modified content.
It uses the same fresh stat/hash/conditional write path, retains audit history of
the prior evidence, and never runs automatically after mismatch. A reappeared
row receiving accepted matching/new evidence clears `reappeared_at` atomically
with that write.

## Selected And Linked Verification

Selection lookup uses `rel_path_key`, never raw separators/case. Selected
verification refreshes only selected paths and does not pay for or infer missing
state across a full location. Post-execution verification contains only eligible
successfully executed operations; no-op or failed operations are not marked
verified merely because they appeared in the plan.

Manual verification is location-scoped and independent of any current plan or
mapping. It must not require both source and target roots.

## Expectations Of Other Modules

- Core supplies integrity/result/event evidence types after DR-14.
- Inventory workflow/repositories supply freshly refreshed canonical selections;
  verifier does not infer inventory or mappings.
- Recorder owns every evidence write and enforces the conditional primitive.
- `COPY_ATTESTED` may provide a baseline digest but never advances
  `last_verified_at`; only an honest verifier read does.
- Dispatcher/session runner supplies custody, checkpoint, and one terminal.
- History observes every item/terminal, including refusal and unexpected error.
- UI consumes typed results and updates inventory rows, not plan rows by loose
  path matching.
- Errors in recorder/history are surfaced separately from content verdicts.

## Latent Features

Worker-count policy may add per-volume multithreading after benchmarks. Results
remain deterministic and each row retains one conditional write. HDD paths may
pipeline IO/CPU without random-seek explosion. Background integrity is an
ordinary dispatcher session. Repair guidance compares both sides against
retained evidence but generates a new plan; verifier never restores content.

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
- Parallel verifier tests, when enabled, preserve one outcome/write per row and
  respect per-volume worker policy.
- Unexpected SQLite/OS errors still produce an audited activity envelope and a
  truthful terminal.
- Import-linter proves verifier imports core but no sibling module.
