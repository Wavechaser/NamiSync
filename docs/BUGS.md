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

- MODERATE - FIXED (2026-07-20). Case-sensitive name reconciliation. A pair
  such as `KEEP.txt` and `keep.txt` was reported as a metadata no-op forever,
  hiding unconverged target casing. Cause: Windows-key grouping discarded target
  spelling before no-op classification; fixed with a typed `case_mismatch`
  blocker and dependency propagation through mismatched directory regions.
- MODERATE - FIXED (2026-07-19). File attribute reconciliation. A readonly,
  hidden, or system attribute change with unchanged size and mtime planned as
  `noop`, leaving the target stale. Cause: equality checked only size and
  timestamp; fixed by including standard attributes and verifying native
  readonly propagation through the CLI workflow.
