# Bug Log

Substantive defects with real behavioral consequences. Cosmetic and style-only
issues are excluded.

Format: `- SEVERITY - STATUS. Category. What happened. (cause: why).`

- **Severity:** SEVERE (data loss, hangs, crashes, or a core feature dead) ·
  MODERATE (disruptive but bounded, or actively misleading) · MINOR (cosmetic
  or no functional harm).
- **Status** reflects the last direct verification of the entry.

---

## EXECUTOR

### M0 hardening

- MODERATE - FIXED (2026-07-19). Availability. A transient sharing violation
  after update backup or move-update publish restarted the operation against
  its own mutation, producing false target drift or destination occupancy.
  (cause: generic retry assumed every operation was idempotent from its start;
  fixed by validated continuation from the last durable sub-step.)

## WORKFLOW AND CLI

### M0 integration

- SEVERE - FIXED (2026-07-19). Availability. Every real execution crashed
  while presenting fresh-preflight results, before mutation could begin.
  (cause: a local `refusal_views` variable shadowed the formatter function;
  fixed by keeping the formatted result under a distinct name.)
- MODERATE - FIXED (2026-07-19). Authorization. A decoded plan's carried
  fingerprint was compared with its commitment without recomputing the plan
  content hash, so altered payload content could retain apparent authorization.
  (cause: two transported fields were compared as if independently derived;
  fixed by recomputing the plan fingerprint before commitment validation.)
- MODERATE - FIXED (2026-07-19). Configuration safety. Identical database
  paths or database overrides inside a managed root were rejected only when
  execution was submitted, after planning and human confirmation.
  (cause: database-location validation lived only on the execution adapter;
  fixed by applying the same read-only validation before plan admission.)

## SCANNER AND PREFLIGHT

### M0 integration

- SEVERE - FIXED (2026-07-19). Availability and convergence. On native Windows
  walks, scanner evidence could omit an NTFS file identity while fresh direct
  observation supplied one, falsely refusing sync and disabling recorded
  correspondence moves. (cause: extended-path `DirEntry.stat()` could report
  inode zero; fixed by an exact-path metadata fallback on stable-ID volumes and
  by treating missing reviewed identity as absent evidence, never a mismatch.)

## PLANNER

### M0 hardening

- MODERATE - FIXED (2026-07-19). Convergence. A readonly, hidden, or system
  attribute change with unchanged size and mtime planned as `noop`, so the
  target attribute never converged. (cause: metadata equality compared only
  size and timestamp; fixed by including standard attributes and proving native
  readonly propagation through the CLI workflow.)
