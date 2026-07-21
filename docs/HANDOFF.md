# NamiSync Session Handoff

Date: 2026-07-21

## Session Outcome

Opt-in source filename casing propagation no longer rewrites metadata-equal
content. Planner emits an explicit zero-byte `recase` operation carrying the
observed and requested spellings; executor performs the existing same-volume
non-replacing rename, creates no trash entry, and recorder updates target
spelling and correspondence while preserving the file's identity and metadata.

Plan-request payloads now require `propagate_source_casing` because it feeds the
policy fingerprint. Ledger command hashes, history hashes and stored detail,
and opaque workflow payloads now share canonical plan JSON's defensive
unpaired-surrogate encoding rule without changing valid-Unicode bytes.

## Changes

- Added `OperationKind.RECASE` and the matching recorder command. It carries
  prior-target evidence, contributes zero content/capacity bytes, and is not an
  update, trash, or identity-move inference.
- Metadata-equal opted-in case changes plan recase. Changed files retain their
  required content update and publish at the requested basename spelling.
- Recase live-checks source and old-target evidence, requires both spellings to
  share one Windows path key, flushes the recorder before mutation, and uses the
  non-replacing rename as the final occupancy guard.
- Default casing behavior remains unchanged: target spelling is preserved.
  Propagation remains latent with no config, CLI, or GUI control and never
  recases parent directories.
- Removed the plan-request decoder's false default for the fingerprinted flag;
  a missing field is rejected instead of silently changing on re-encode.
- Added surrogate-safe JSON byte/text helpers at the workflow and history
  boundaries plus defensive ledger hash encoding. Hostile history detail
  round-trips through SQLite; valid Unicode retains its established encoding.
- Updated core, planner, preflight, executor, recorder, history, workflow,
  architecture, feature, bug-log, README, and handoff documentation.

## Verification

- Focused recase/payload/JSON regression selection: 15 passed in 0.31s.
- Complete payload codec suite: 8 passed in 0.09s.
- Full suite: 307 passed in 8.24s.
- Import-linter: 7 contracts kept, 0 broken (41 files, 137 dependencies).
- `git diff --check`: clean apart from expected LF-to-CRLF notices.
- Native Windows recase coverage verifies identity preservation, requested
  directory-entry spelling, zero bytes, and no `.synctrash` creation.

## Immediate Next Context

- `propagate_source_casing` remains false and unexposed by default. A future
  settings/UI surface can bind it without another plan or payload shape change.
- A prior plan-request payload missing the fingerprinted flag is intentionally
  invalid and must be planned again; decoding it as false would not be a
  lossless semantic round trip.
- Recase is safe in the incomplete-scan additive subset because it validates
  both known entries and cannot overwrite a distinct destination. Move,
  move-update, trash, and delete remain withheld.
- JSON backslash escaping is defense in depth, not permission for malformed
  path code units. `validate_relative_path` continues to reject unpaired
  surrogates before filesystem evidence or operation paths are constructed.
