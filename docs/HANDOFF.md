# NamiSync Session Handoff

Date: 2026-08-08
Branch: `milestone1`

## Session Outcome

Implemented the planned M1 safety-audit hardening while preserving the
"show full intent, execute only the safe selection" contract.

- H1/H2 remain full-plan review behavior: blocked parent/type conflicts,
  inherited blocked copies, unsupported source rows, and their policy removals
  stay visible. Focused regressions prove the derived safe selection defers the
  matching removal/dependencies under both `trash` and `mirror` while unrelated
  safe removal remains executable. Planner production code did not change.
- H3 moves UPDATE/DELETE recorder waits before their final destructive guard.
  An external replacement introduced during the wait is detected and preserved;
  the smaller path-stat-to-syscall external-writer boundary remains documented.
- H4 settles post-publish COPY/UPDATE/MOVE_UPDATE failure from durable state
  before temp cleanup, including commit-then-raise and failed state-probe cases.
  It reports target/backup/old-path truth, degrades recording, and publishes no
  success-only evidence.
- H5 advances the reset-only ledger to v3 with constrained sticky verification
  invalidation. Scan and verifier drift, including a disappearance after
  refresh, conditionally invalidate; hash mismatch dominates metadata drift;
  guarded replacement evidence clears the marker; stale queries, CLI output,
  and four-state inventory projection consume it.
- H6/M9/M10 give every dispatcher worker attempt a process-local generation
  that owns its reservations and lease. One current attempt survives each
  pause/resume/cancel retirement handoff, stale cleanup cannot touch a
  successor, Windows lease release stays on the acquiring thread, and shutdown
  reports canceled acquisitions or terminal-but-not-retired attempts.
- Updated the active architecture, component, feature, command-line, database,
  audit-resolution, README changelog, and defect-ledger documentation. The
  historical hash/M1 plans now point to the active ledger-v3 boundary.

## Verification

- Complete pytest suite: `1121 passed, 1 skipped in 35.78s`. The skip is the
  optional real directory-symlink substitution test on a host without symlink
  privilege; deterministic path-guard coverage remains active.
- Pytest promotes `PytestUnhandledThreadExceptionWarning` to an error, guarding
  the original duplicate-worker failure surface.
- Import linter: `8 kept, 0 broken` across 50 files and 185 dependencies.
- Focused final executor uncertainty regression: `3 passed` (including both
  pre- and post-commit replace faults).
- `git diff --check`: clean; only the repository's expected LF-to-CRLF notices
  were emitted by later diff inspection.

## Adversarial Review And Next Context

- Separate planner/executor, integrity/schema, and dispatcher reviews were run.
  They drove deterministic generation-handoff coverage, stricter schema and
  negative-recording tests, hash-mismatch dominance, missing-after-refresh
  invalidation, publish-then-raise probing before cleanup, and conservative
  publication-unverified settlement.
- One newly identified lower-severity residual is recorded OPEN in `BUGS.md`:
  MOVE, RECASE, MOVE_UPDATE old-path cleanup, and TRASH still place their
  operation-specific recorder wait between a path guard and non-replacing
  rename. An external writer can therefore cause recoverable relocation or
  wrong-version settlement. Do not generalize the UPDATE/DELETE guarantee until
  those four barriers move before their final guards with gated regressions.
- Ledger v3 is an intentional pre-migrator reset boundary. Ledger v1-v2 and
  mismatched contract markers are refused without mutation; reset both local
  databases together. There is no evidence migration in this stage.
- M1 Stage 6 remains the next product delivery surface after this hardening.
