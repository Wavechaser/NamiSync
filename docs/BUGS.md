# Bug Log

Substantive defects with real behavioral consequences. Cosmetic and style-only
issues are excluded.

Each entry records `SEVERITY - STATUS (YYYY-MM-DD)`, then a failure-specific
category, the observed behavior and consequence, `Cause: why`, and, when fixed,
the corrective change. The behavior and fix are written in natural prose rather
than as separate labels.

- **Severity:** SEVERE (data loss, hangs, crashes, or a core feature dead) ·
  MODERATE (disruptive but bounded, or actively misleading) · MINOR (cosmetic
  or no functional harm).
- **Status** reflects the last direct verification of the entry.
- **Category** names the failure boundary, not a broad outcome such as
  availability or convergence.

Entries are module/function-first, not a project-wide timeline: `##` headings
are owning modules or feature boundaries, and `###` headings are their
functional scope or delivery phase. Add an entry under the module/function that
owns the behavior, retain its relevant subheading, and keep entries newest first
within that section. Do not add date-based sections or append unrelated entries
to a global chronological list.

---

## EXECUTOR

### M0 hardening

- MODERATE - FIXED (2026-07-20). Orphaned temporary-file recovery. Temps left
  by killed or crashed runs accumulated permanently while preflight counted
  their bytes as reclaimable, leaking target capacity and potentially stranding
  a nearly-full sync. Cause: executor removed only the current run's exact
  per-operation temp, while every rerun has a new run id and scanner correctly
  ignores owned temps; fixed with one post-preflight, pre-copy exact-grammar
  sweep over preflight's touched target parents, excluding current-run files and
  `.synctrash`.
- MODERATE - FIXED (2026-07-20). Metadata state validation. Cleanup of a
  directory emptied by same-run moves or trash operations was rejected as target
  drift, preventing folder rename/removal in one run. Cause: the final guard
  compared scan-time mtime and link count that planned child removal changes;
  fixed with a cleanup matcher that validates stable metadata and treats absent
  reviewed identity as absent evidence before atomic empty-directory removal.
- MODERATE - FIXED (2026-07-20). Platform API permission. Every Windows
  parent-directory flush failed and warned despite successful mutations. Cause:
  `CreateFileW` requested `GENERIC_READ`, while `FlushFileBuffers` requires
  write access; fixed by requesting `GENERIC_WRITE` on the existing directory
  handle.
- MODERATE - FIXED (2026-07-19). Idempotency failure. A transient sharing
  violation after update backup or publish restarted against the operation's own
  mutation, causing false target drift or destination occupancy. Cause: generic
  retry assumed every operation could restart; fixed by validated continuation
  from the last durable sub-step.

## WORKFLOW AND CLI

### M0 integration

- MODERATE - FIXED (2026-07-21). Rename plan presentation. Recase rows rendered
  the source and destination as the same spelling, and move/move-update rows
  likewise omitted the old target path, so review hid the filesystem rename a
  user was approving. Cause: `PlanOperationView` discarded
  `prior_target_rel_path` and the CLI always used the source path as the
  displayed origin; fixed by retaining `prior_target_path` in the workflow read
  model and preferring it as the left side for rename-shaped operations.
- MODERATE - FIXED (2026-07-21). Fingerprinted option decoding. A plan-request
  payload that omitted `propagate_source_casing` decoded as false and then
  re-encoded with the field present, so one accepted payload did not have a
  byte-stable semantic round trip for an input to `policy_fingerprint`. Cause:
  the newly added flag alone used `.get(..., False)` while every neighboring
  semantic option was required; fixed by requiring the field during decode and
  retaining explicit round-trip coverage.
- SEVERE - FIXED (2026-07-20). Safe partial execution. One blocked item or an
  incomplete scan refused the whole sync, while simply omitting blockers could
  expose target-only deletion from incomplete source evidence. Cause: workflow
  selected every operation and preflight gated the whole run; fixed with
  commitment-bound safe-subset selection, dependency quarantine, additive-only
  incomplete-scan fallback, and preflight enforcement.
- MODERATE - FIXED (2026-07-20). Execution outcome reporting. Blocked plan
  items were absent from results and history because only selected operations
  emitted outcomes. Cause: the outcome model had no blocker state and workflow
  emitted no exclusions; fixed with `BLOCKED`, reasoned `DEFERRED` exclusions,
  itemized history rows, and a version-2 blocked summary count.
- SEVERE - FIXED (2026-07-19). Result presentation crash. Every real execution
  crashed while presenting fresh-preflight results, before mutation began.
  Cause: local `refusal_views` shadowed the formatter; fixed by using a distinct
  result variable.
- MODERATE - FIXED (2026-07-19). Plan integrity validation. A decoded plan's
  carried fingerprint was compared with its commitment without recomputing the
  content hash, allowing altered payloads to appear authorized. Cause: two
  transported fields were treated as independently derived; fixed by recomputing
  the fingerprint before commitment validation.
- MODERATE - FIXED (2026-07-19). Configuration preflight validation. Identical
  database paths or overrides inside a managed root were rejected only after
  planning and confirmation. Cause: location validation lived only on the
  execution adapter; fixed by applying it before plan admission.

## SCANNER AND PREFLIGHT

### M0 integration

- MINOR - FIXED (2026-07-21). Defensive JSON encoding consistency. Path
  validation prevented unpaired surrogates from reaching ledger/history
  records, but ledger idempotency hashing, history hashing/detail storage, and
  opaque workflow payload encoding would still raise if a malformed code unit
  arrived through free-form detail or a future relaxed boundary. Cause: only
  canonical plan JSON used the defensive final UTF-8 encoding rule; fixed by
  applying the same valid-Unicode-compatible backslash escaping at all three
  module boundaries and round-tripping hostile history detail in tests.
- SEVERE - FIXED (2026-07-20). Unsafe filename isolation. One NTFS, SMB,
  archive, or WSL-originated name outside NamiSync's relative-path contract
  could abort planning; an unpaired surrogate could later crash ID or fingerprint
  encoding. Cause: the walker normalized untrusted names too early, validation
  admitted surrogates, and canonical JSON required UTF-8; fixed with pre-use
  validation, typed escaped evidence, incomplete-scan isolation, surrogate
  rejection, and compatible serializer hardening.
- SEVERE - FIXED (2026-07-19). File identity acquisition. Windows scan evidence
  could omit an NTFS file identity while fresh observation supplied one, falsely
  refusing sync and disabling correspondence moves. Cause: extended-path
  `DirEntry.stat()` could report inode zero; fixed with an exact-path fallback
  on stable-ID volumes and absent-identity-as-absent-evidence matching.

## PLANNER

### M0 hardening

- MODERATE - FIXED (2026-07-21). Opt-in casing propagation cost. A
  metadata-equal case-only filename change was represented as `update`, causing
  a full source-content rewrite, capacity charge, and trash backup merely to
  change directory-entry spelling. Cause: the first propagation seam reused the
  only operation that could publish a requested spelling; fixed with an
  explicit zero-byte `recase` operation that carries old/new spellings, uses a
  same-volume non-replacing rename, preserves identity/metadata, records updated
  correspondence, and creates no trash entry.
- MODERATE - FIXED (2026-07-21). Filename-form advisory execution. A
  case-only source/target filename pair blocked even when source metadata had
  changed, suppressing the required update; canonically equivalent NFC/NFD
  spellings were instead misclassified as unrelated copy/removal work with no
  warning. Cause: the initial casing fix made spelling visibility a conflict
  gate, and planning compared only Windows case keys without a conservative
  canonical-equivalence advisory pass; fixed by retaining normal update/no-op
  semantics under typed non-blocking reasons, preserving target spelling by
  default, adding a fingerprinted but currently unexposed source-basename
  recasing option, and pairing only unique same-parent NFC-equivalent files that
  are not already exact matches.
- MODERATE - FIXED (2026-07-20). Case-sensitive name reconciliation. A pair
  such as `KEEP.txt` and `keep.txt` was reported as a metadata no-op forever,
  hiding unconverged target casing. Cause: Windows-key grouping discarded target
  spelling before no-op classification; initially made visible with a typed
  `case_mismatch` blocker. The 2026-07-21 follow-up above retains that typed
  visibility without suppressing content work.
- MODERATE - FIXED (2026-07-19). File attribute reconciliation. A readonly,
  hidden, or system attribute change with unchanged size and mtime planned as
  `noop`, leaving the target stale. Cause: equality checked only size and
  timestamp; fixed by including standard attributes and verifying native
  readonly propagation through the CLI workflow.
