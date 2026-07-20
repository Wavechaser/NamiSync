# NamiSync Session Handoff

Date: 2026-07-20

## Session Outcome

Restored empty-directory cleanup on targets that do not provide stable file
identities, including FAT-style volumes. The executor now follows the shared
evidence rule: identity binds exactly when the reviewed scan supplied it;
absent identity is absent evidence rather than an execution veto.

## Changes

- Narrowed only the `directory_cleanup` guard. It continues to ignore the
  directory mtime and link-count churn caused by successful child operations.
- The guard still requires exact directory kind, size, attributes, and creation
  time. When a reviewed identity exists, a replacement directory is still
  rejected as target drift.
- `RemoveDirectory`/`rmdir` remains the final atomic emptiness check, so cleanup
  cannot remove a directory containing entries.
- Replaced the identity-veto regression with an identity-less convergence test
  and added a counter-test proving immutable metadata drift is still rejected.
- Updated `BUGS.md`, `EXECUTOR.md`, `FEATURES.md`, `ARCHITECTURE.md`, and the
  README changelog to describe the conditional-identity policy.

## Verification

- Directory-cleanup regression selection: 6 passed.
- Focused executor suite: 52 passed.
- Full suite: 288 passed in 7.41s.
- Import-linter: 7 contracts kept, 0 broken (41 files, 137 dependencies).
- `git diff --check`: clean apart from expected LF-to-CRLF notices.

## Immediate Next Context

- The residual external-writer boundary is deliberate: on an identity-less
  target, a recreated empty directory could pass the remaining evidence checks.
  The operating system still refuses deletion if the directory contains an
  entry.
- The relaxed matcher remains exclusive to dependency-complete
  `directory_cleanup` deletes. File deletes and all other operation guards keep
  their existing evidence rules.
