# NamiSync Session Handoff

Date: 2026-07-20

## Session Outcome

Fixed two scanner/planner input-boundary defects. A filesystem entry whose raw
name is legal to enumerate but outside NamiSync's safe relative-path contract
no longer aborts scan/plan review, and a source/target pair that differs only in
exact casing no longer disappears into a misleading metadata no-op.

The fixes preserve the existing safety boundary: hostile names never enter
path-bearing records or executable operations, and M0 does not attempt an
automatic case-only rename through the ordinary absence-guarded move contract.

## Changes

- `validate_relative_path()` now rejects unpaired surrogate code units in
  addition to the existing traversal, qualification, device, stream, NUL, and
  ambiguous-suffix rules.
- The walking scanner validates each raw child path before canonical sorting,
  ignore evaluation, metadata access, or record construction. An invalid file
  or directory becomes an escaped `PATH_UNREPRESENTABLE` warning at its nearest
  valid parent, makes the scan incomplete, is not opened or descended, and does
  not prevent safe siblings from being retained.
- Canonical JSON retains its established UTF-8 bytes for valid Unicode while
  defensively emitting JSON escapes for malformed surrogate code units, so
  operation-id and plan-fingerprint construction cannot raise a raw
  `UnicodeEncodeError`.
- The planner emits a distinct blocked `case_mismatch` operation when one
  source and target file or directory share a Windows key but differ in exact
  spelling. Directory conflicts block dependent descendant work.
- Added synthetic hostile-file/directory coverage, a real Windows
  `\\?\...\trailingdot.` regression, canonical serialization coverage, and
  matching/changed-metadata file plus directory case-mismatch coverage.
- Updated `SCANNER.md`, `PLANNER.md`, `CORE.md`, `BUGS.md`, `FEATURES.md`,
  `ARCHITECTURE.md`, README status/changelog, and this handoff.

## Verification

- Focused scanner/planner/path tests: 59 passed.
- Payload/workflow/CLI/preflight compatibility tests: 61 passed.
- Full suite: 287 passed in 8.17s.
- Import-linter: 7 contracts kept, 0 broken (41 files, 137 dependencies).
- `git diff --check`: clean apart from expected Git LF-to-CRLF notices.

## Immediate Next Context

- `PATH_UNREPRESENTABLE` is diagnostic evidence; `complete=False` is the safety
  state that withholds absence- and identity-dependent work. Invalid raw names
  are intentionally not forced into `UnsupportedRecord`, whose path contract
  must remain safe.
- Exact-case mismatches remain blocked until a future dedicated recase
  operation defines target-local guards, executor behavior, recording, and
  crash recovery. Reusing ordinary `MOVE` would be incorrect because its target
  must be absent, while old and new case spellings may resolve to one live item.
- Canonical bytes and fingerprints for every valid-Unicode plan are unchanged;
  only malformed surrogate code units use the defensive JSON escape path.
