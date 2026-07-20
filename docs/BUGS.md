# Bug Log

Substantive defects with real behavioral consequences. Cosmetic and style-only
issues are excluded.

Format: `- SEVERITY - STATUS. Category. What happened. Cause: why.`

- **Severity:** SEVERE (data loss, hangs, crashes, or a core feature dead) ·
  MODERATE (disruptive but bounded, or actively misleading) · MINOR (cosmetic
  or no functional harm).
- **Status** reflects the last direct verification of the entry.

---

## EXECUTOR

### M0 hardening

- MODERATE - FIXED (2026-07-20). Availability and convergence. Dependency-
  ordered cleanup of a directory emptied by same-run moves or trash operations
  always failed as target drift, preventing folder rename/removal from finishing
  in one run. Cause: the generic final guard compared the directory's scan-time
  mtime and link count even though removing its planned children changes those
  fields; fixed with a cleanup-only matcher that still requires kind, size,
  attributes, and creation time, binds identity when the reviewed scan supplied
  it, and treats absent identity as absent evidence rather than a veto before
  atomic empty-directory removal.
- MODERATE - FIXED (2026-07-20). Durability reporting. Every Windows parent-
  directory flush failed and attached an unsupported-flush warning to otherwise
  successful mutations. Cause: `CreateFileW` opened the directory for
  `GENERIC_READ` even though `FlushFileBuffers` requires write access; fixed by
  using `GENERIC_WRITE` with the existing `FILE_FLAG_BACKUP_SEMANTICS` handle.
- MODERATE - FIXED (2026-07-19). Availability. A transient sharing violation
  after update backup or move-update publish restarted the operation against
  its own mutation, producing false target drift or destination occupancy.
  Cause: generic retry assumed every operation was idempotent from its start;
  fixed by validated continuation from the last durable sub-step.

## WORKFLOW AND CLI

### M0 integration

- SEVERE - FIXED (2026-07-20). Availability and data safety. One blocked item
  or any incomplete scan refused the entire sync, so independent ordinary files
  could never converge; merely dropping the blocker would instead have exposed
  target-only trash/delete planned from incomplete source knowledge. Cause: the
  workflow selected every plan operation and preflight treated completeness as
  a run-wide gate; fixed with commitment-bound safe-subset selection, blocked-
  path/dependency quarantine, additive-only incomplete-scan fallback, and an
  independent preflight backstop against reintroduced unsafe selections.
- MODERATE - FIXED (2026-07-20). Audit truth. Blocked plan items disappeared
  from execution results/history because only executor-selected operations
  emitted item outcomes. Cause: the five-value outcome model had no direct
  blocker state and workflow emitted no exclusion events; fixed with the sixth
  `BLOCKED` outcome, reasoned `DEFERRED` exclusions, itemized history rows, and
  a version-2 blocked summary count.
- SEVERE - FIXED (2026-07-19). Availability. Every real execution crashed
  while presenting fresh-preflight results, before mutation could begin.
  Cause: a local `refusal_views` variable shadowed the formatter function;
  fixed by keeping the formatted result under a distinct name.
- MODERATE - FIXED (2026-07-19). Authorization. A decoded plan's carried
  fingerprint was compared with its commitment without recomputing the plan
  content hash, so altered payload content could retain apparent authorization.
  Cause: two transported fields were compared as if independently derived;
  fixed by recomputing the plan fingerprint before commitment validation.
- MODERATE - FIXED (2026-07-19). Configuration safety. Identical database
  paths or database overrides inside a managed root were rejected only when
  execution was submitted, after planning and human confirmation.
  Cause: database-location validation lived only on the execution adapter;
  fixed by applying the same read-only validation before plan admission.

## SCANNER AND PREFLIGHT

### M0 integration

- SEVERE - FIXED (2026-07-20). Availability and input safety. A single NTFS,
  SMB, archive, or WSL-originated name outside NamiSync's relative-path contract
  could abort the whole planning session with a raw `PathValidationError`; an
  unpaired surrogate could instead survive scanning and crash operation-id or
  fingerprint encoding with `UnicodeEncodeError`. Cause: the walker normalized
  untrusted directory-entry names before its per-entry boundary, path validation
  admitted surrogate code units, and canonical JSON used strict UTF-8 encoding;
  fixed by pre-use validation, escaped typed `PATH_UNREPRESENTABLE` evidence,
  incomplete-scan isolation, explicit surrogate rejection, and compatible
  serializer hardening.
- SEVERE - FIXED (2026-07-19). Availability and convergence. On native Windows
  walks, scanner evidence could omit an NTFS file identity while fresh direct
  observation supplied one, falsely refusing sync and disabling recorded
  correspondence moves.
  Cause: extended-path `DirEntry.stat()` could report inode zero; fixed by
  an exact-path metadata fallback on stable-ID volumes and by treating missing
  reviewed identity as absent evidence, never a mismatch.

## PLANNER

### M0 hardening

- MODERATE - FIXED (2026-07-20). Convergence truth. A source/target pair such
  as `KEEP.txt` and `keep.txt` was reported as a metadata no-op forever, hiding
  the fact that exact target casing had not converged. Cause: Windows-key
  grouping discarded the target spelling before no-op classification; fixed
  with a distinct typed `case_mismatch` blocker for files and directories plus
  blocked dependency propagation through mismatched directory regions.
- MODERATE - FIXED (2026-07-19). Convergence. A readonly, hidden, or system
  attribute change with unchanged size and mtime planned as `noop`, so the
  target attribute never converged.
  Cause: metadata equality compared only size and timestamp; fixed by including
  standard attributes and proving native readonly propagation through the
  CLI workflow.
