# NamiSync Session Handoff

Date: 2026-08-09
Branch: `milestone1`

## Session Outcome

Restored FULL scan availability when a managed root is exactly a trusted
folder-mounted volume anchor, without relaxing the managed-root redirection
contract or changing workflow, schema, or persistence formats.

- Mount-root admission requires normalized agreement among the resolved root,
  reviewed/current trusted anchor, and the current volume-evidence mount path.
  A caller-provided anchor alone is not authority.
- The scanner no-follow stats the mount entry for classification, then follows
  metadata only for that exact authorized root. Its `DirRecord` and visited
  identity therefore describe the mounted volume rather than the host-volume
  reparse entry.
- Placeholder anchors, mismatched evidence, missing/non-directory/still-reparse
  followed state, configured-root junctions, subtree starts, and descendant
  reparses remain refused or untraversed. Existing pre/post anchor and full
  `VolumeId` checks still bracket enumeration.
- Ordinary roots plus PATHS and SUBTREES scans add no followed-root stat.

## Verification

- Focused mount-root and reparse guard matrix: `29 passed`.
- Complete scanner suite: `55 passed`; inventory runtime/workflow: `39 passed`.
- Cross-layer scanner/inventory/bridge/core gate: `157 passed, 1 skipped`.
- Complete partitioned pytest gate: `1321 passed, 2 skipped`.
- Import linter: `8 kept, 0 broken` across 50 files and 189 dependencies.
- Python compile and `git diff --check` passed.
- Two independent adversarial implementation reviews and one documentation
  review found no remaining authority, metadata-identity, placeholder, scope,
  descendant-reparse, or contract blocker.

## Immediate Next Context

- Prepared-temp same-object byte mutation and identity-weak substitution remain
  an explicitly accepted residual boundary. Closing them would add a byte
  reread or handle-bound publication cost that the current performance-focused
  threat contract does not justify.
- Scoped PATHS/SUBTREES observation validates each requested final start but
  does not yet no-follow validate every intermediate component inside the
  requested relative path. This predates the trusted mount-root fix and was not
  widened or claimed closed here; review it separately before broadening scoped
  inventory authority.
- `test_paused_verify_resumes_without_repeating_or_losing_items` still exposes
  deferred M1 behavior: dispatcher `PAUSED` can become poll-visible before the
  audit window exists, so an immediate history summary lookup can raise
  `KeyError`. This delivery does not mask or modify that test/behavior.
