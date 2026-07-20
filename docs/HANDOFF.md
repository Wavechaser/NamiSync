# NamiSync Session Handoff

Date: 2026-07-20

## Session Outcome

Fixed two M0 executor defects that prevented dependency-ordered directory
cleanup and made every Windows parent-directory durability flush fail. Those
executor fixes changed no deferred feature scope or public contract.

Added M0 automatic safe-subset execution so blocked items and incomplete scans
no longer refuse independent safe work. Destructive and identity-move work stays
withheld whenever scan completeness cannot prove it safe, and blocked-path
counterparts remain quarantined.

## Changes

- `DELETE` operations marked `directory_cleanup` now use a dedicated final
  guard. It requires a reviewed stable directory identity and exact kind, size,
  standard attributes, and creation time, while ignoring only mtime and link
  count changes caused by successful child move/trash dependencies.
- Identity-less cleanup, replacement directories, file deletes, non-cleanup
  directory operations, and nonempty directories remain guarded/refused.
- `NativeFileSystem.flush_directory` now opens Windows directory handles with
  `GENERIC_WRITE`, the access required by `FlushFileBuffers`, while retaining
  broad sharing, `OPEN_EXISTING`, and `FILE_FLAG_BACKUP_SEMANTICS`.
- Best-effort flush failure still preserves filesystem success and emits an
  explicit durability warning.
- Added focused regressions for trash/move cleanup, replacement and
  identity-less refusal, file-evidence isolation, nonempty refusal, successful
  native NTFS flush, and injected flush degradation.
- Updated `docs/BUGS.md`, `docs/EXECUTOR.md`, `docs/FEATURES.md`,
  `docs/ARCHITECTURE.md`, and the README changelog.
- Added deterministic workflow selection and a matching pure-preflight
  backstop: direct blockers are `BLOCKED`; correspondence/dependency collateral
  and incomplete-scan destructive work are `DEFERRED`; copy/update/mkdir/noop
  remain runnable, while move/move-update/trash/delete are withheld for either
  incomplete scan.
- Review and commitment now use the derived selection and selected capacity.
  Workflow emits exclusions into terminal results/history without writing them
  to the main ledger; guarded no-ops still refresh correspondence.
- Added `BLOCKED` as the sixth outcome, partial CLI exit code 6, itemized
  completed-with-exceptions output, history `blocked_count`, event schema v2,
  and a transactional history v1-to-v2 additive migration.
- Updated workflow, preflight, planner, scanner, executor, recorder, core,
  database, history, interface/CLI, feature, architecture, bug, README, and
  handoff documentation for the new contract.

## Verification

- `python -m pytest tests/test_executor.py -q`: 51 passed.
- `python -m pytest -q`: 280 passed.
- Import-linter: 7 contracts kept, 0 broken (41 files, 137 dependencies).
- `git diff --check`: clean apart from expected Git LF-to-CRLF notices.
- Safe-subset focused verification: 87 tests passed across workflow, preflight,
  history, CLI, and schema areas before the final full-suite run.

## Immediate Next Context

- Parent-directory flushing remains explicitly best effort; a refused or
  unsupported flush is reported without relabeling a completed mutation.
- Cleanup on a filesystem without reviewed stable identity intentionally
  refuses rather than risking removal of a reused empty directory path.
- The executor still uses path-based `rmdir`; `RemoveDirectory` supplies the
  atomic nonempty refusal, while external path replacement remains within the
  documented external-writer boundary.
- Incomplete scans deliberately use a global additive fallback because `Plan`
  currently carries completeness booleans, not exact uncertainty regions. A
  future precision improvement can persist source/target uncertainty regions
  and narrow withholding without changing the selection/outcome seam.
- `BLOCKED` is the only new top-level outcome. Quarantine and incomplete-scan
  withholding remain `DEFERRED` reasons, avoiding separate result/schema axes.
