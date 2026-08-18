# Session Handoff

Status (2026-08-18): the development benchmark rig is streamlined and its
workspace/artifact lifecycle is hardened. The implementation, focused tests,
and owning `TOOLS`/`TESTS`/`BUGS` documentation landed in `cef1aa2`; this
handoff records the final documentation and repository-wide verification sweep.

## Delivered

- Split executor benchmarking into explicit preparation and execution seams.
  The default empty-target COPY/MKDIR profile resets before each sample,
  scans/plans once, optionally preflights the first fresh execution set, and
  feeds the immutable in-memory plan to fresh run IDs, tapes, recorders,
  backends, and filesystems for every measured copy-plus-finishing sample.
  `--prepare-each` retains the guarded full-chain path; template and
  target-dependent plans never reuse stale preparation.
- Kept diagnostics enabled by default and made them useful without a report.
  Executor samples print backend/outside-backend, blocking/starvation,
  high-water/reserved-byte, and chunk-size details; verifier samples print
  open/read/outside-read timing. Repeated commands print N/minimum/median/
  maximum run time and median sample throughput. `--no-metrics`, `--no-tap`,
  and `--no-preflight` remain explicit opt-outs.
- Bound each executor/verifier batch to one fixture. Static executor repeats
  require stable published digest/size evidence and a final source rescan;
  verifier samples match primed/synthetic/sidecar setup evidence or the first
  no-evidence sample, with repeated baselining content comparison when the real
  hasher is active. Drift invalidates the whole batch.
- Replaced marker-wide descendant deletion with a strict sibling output
  manifest. Exact cleanup re-binds manifest path, identity, schema, and entries,
  validates the complete live tree before mutation, revalidates each entry, and
  uses individual unlink/deepest-first `rmdir`. `clean --force-all` prints every
  path and applies only that displayed plan; unknown or late paths are preserved.
- Made deletion receipts state the resolved root, authority, counts, bytes,
  exact forced paths, completed partial paths, and retained root/marker/manifest
  state. Generator/template reset completion is printed before repopulation;
  failed executor receipts validate a manifest rather than trusting its name.
- Made reports one create-exclusive, versioned, atomic invocation envelope with
  separate configuration, batch preparation, samples, batch validation, and
  summary. Existing reports require `--replace-report`. Baseline sidecars remain
  distinct retained input evidence, require explicit paths, and bind
  `--replace-sidecar` authority before the priming pass. Default console runs
  create no report or sidecar artifact.

## Adversarial Review

- Independent benchmark, cleanup, and documentation reviewers challenged the
  builder checkpoint before commit. Their findings closed verifier
  setup-to-sample drift, invisible default reader diagnostics, duplicate timing
  attribution, missing plan/sidecar provenance, and a MOVE_UPDATE output-model
  mismatch.
- Cleanup review found that an early force implementation recomputed its plan
  after printing it, canonicalized requested aliases before admission, and
  allowed a caller-constructed non-forced plan to bypass manifest authority.
  The final seam applies the printed immutable plan, checks every existing path
  component for generic reparse attributes, and re-proves non-forced plan
  provenance against the bound manifest.
- Artifact review found sidecar replacement identity was captured after a long
  priming pass and failure receipts could call a stale template manifest exact.
  Destination identity is now captured before work and revalidated at publish;
  failure receipts run live cleanup validation and give the recovery command.
- Partial-state review covered per-entry errors, post-delete validation,
  disappeared/replaced manifests, root/marker retirement, and
  `KeyboardInterrupt`. Hostile manifest tests cover malformed/duplicate/
  unsorted rows, wrong root binding, size bounds, hard links, generic reparses,
  forged plans, and publication occupant swaps.
- The retained executor settlement oracle and its baseline were neither changed
  nor run. This task changed development benchmark composition and safety, not
  production executor settlement policy.

## Verification

- Focused executor/verifier/corpus/CLI checkpoint suite: `155 passed, 3 skipped`
  before the final hostile-manifest and opt-out additions; every added regression
  was then exercised directly and by the final department/full runs.
- Final tools department: `251 passed, 3 skipped, 2270 deselected`. All three
  skips require unavailable Windows symlink privileges; generic-reparse paths
  retain non-symlink synthetic coverage.
- Final ordinary repository suite: `2,483 passed, 14 skipped, 27 deselected` in
  `122.00s`.
- Import boundary lint: `11 kept, 0 broken` across 71 files and 253 dependencies.
- `git diff --check` and the stale-text scan for old JSONL append, per-repeat
  preparation, median-throughput, and recursive-clean wording are clean apart
  from expected working-copy CRLF notices.

## Remaining Work

- Static plan reuse is intentionally limited to owned empty-target COPY/MKDIR
  workloads. Templates, updates, deletions, NOOPs, correspondence-backed moves,
  and other target-dependent profiles continue to prepare every sample.
- Executor reads are buffered repeated-source/warm-profile observations. A
  same-size/same-mtime content change completed before the first sample and then
  held stable is outside the stat-only preparation anchor; use a quiescent
  source. `--null-hasher` likewise cannot detect same-stat content drift.
- Reports are deliberate per-invocation files, not an append stream or stdout
  protocol. Sidecar JSONL remains explicit retained verifier evidence. Workspace
  cleanup never guesses either artifact; an unrecognized sibling output
  manifest is preserved for manual inspection/removal before name reuse.
- Throughput and pipeline/read timings remain Tier 0 diagnostics. No release
  gate, production acceptance limit, settlement-oracle change, or README-level
  product behavior follows from these measurements.
