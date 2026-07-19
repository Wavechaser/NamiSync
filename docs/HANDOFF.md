# NamiSync Session Handoff

Date: 2026-07-20

## Session Outcome

Fixed two M0 executor defects that prevented dependency-ordered directory
cleanup and made every Windows parent-directory durability flush fail. No
deferred feature scope or public contract changed.

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

## Verification

- `python -m pytest tests/test_executor.py -q`: 51 passed.
- `python -m pytest -q`: 264 passed.
- Import-linter: 7 contracts kept, 0 broken (40 files, 133 dependencies).
- `git diff --check`: clean apart from expected Git LF-to-CRLF notices.

## Immediate Next Context

- Parent-directory flushing remains explicitly best effort; a refused or
  unsupported flush is reported without relabeling a completed mutation.
- Cleanup on a filesystem without reviewed stable identity intentionally
  refuses rather than risking removal of a reused empty directory path.
- The executor still uses path-based `rmdir`; `RemoveDirectory` supplies the
  atomic nonempty refusal, while external path replacement remains within the
  documented external-writer boundary.
