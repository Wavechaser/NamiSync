# NamiSync Session Handoff

Date: 2026-08-08
Branch: `milestone1`

## Session Outcome

Closed the rename durability-wait race recorded during the adversarial review
of `cf186a8`.

- MOVE, RECASE, MOVE_UPDATE old-path cleanup, and TRASH previously performed a
  recorder flush after their source/path guard and before a non-replacing
  rename. An external writer could replace the guarded path during that wait;
  MOVE/RECASE could relocate the foreign occupant before failing their later
  stat, while MOVE_UPDATE/TRASH could falsely settle success.
- Every affected operation now flushes prior recorder evidence before its final
  mutation-relevant source/destination guards. A same-size/same-mtime foreign
  replacement with a different stable identity is rejected as `target-drift`
  and remains at the original path; no rename, trash move, or ledger command
  occurs.
- MOVE_UPDATE performs a preliminary state read only to recognize an already
  committed retry. When the old path is still live it flushes, re-reads both old
  and trash paths, then guards and renames. A reported failure after a committed
  rename therefore converges without a redundant pre-mutation flush, while a
  genuinely uncommitted retry receives a fresh barrier and guards.
- Updated `BUGS.md` from OPEN to FIXED and synchronized the executor, recorder,
  architecture, feature, audit-resolution, README changelog, and handoff
  contracts. The smaller pathname-guard-to-syscall external-writer interval is
  still explicitly non-atomic.

## Verification

- Reproduction before the fix: all four parameter cases failed; MOVE_UPDATE and
  TRASH demonstrated false-success settlement.
- Focused final guard coverage: `6 passed` across UPDATE, DELETE, MOVE, RECASE,
  MOVE_UPDATE, and TRASH.
- Complete executor suite: `186 passed`.
- Complete pytest suite: `1125 passed, 1 skipped in 45.86s`. The skip is the
  optional real directory-symlink substitution test on a host without symlink
  privilege; deterministic guard coverage remains active.
- Import linter: `8 kept, 0 broken` across 50 files and 185 dependencies.
- `git diff --check`: clean; Git reports only the repository's expected
  LF-to-CRLF working-copy notices during diff inspection.

## Immediate Next Context

- Do not describe path-based guards as compare-and-swap. External writers remain
  outside NamiSync's volume-lock authority and can still replace a pathname in
  the short interval between its final stat and syscall. Conditional primitives
  continue to guarantee only destination absence or directory emptiness.
- M1 Stage 6 remains the next product delivery surface after this hardening.
