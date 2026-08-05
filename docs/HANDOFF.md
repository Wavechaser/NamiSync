# NamiSync Session Handoff

Date: 2026-08-04
Branch: `milestone1`

## Session Outcome

Closed the post-publication retry drift defect found in the review of
`0aafeb3^..HEAD` with the deliberately minimal identity/stat fix.

- COPY, UPDATE, and MOVE_UPDATE now share one guard when an execution attempt
  enters with an already-published retry continuation.
- The guard compares the current profiled target version with the cached
  published stat; before that stat exists it compares kind/size plus stable
  identity when available while allowing repairable mtime drift.
- A missing or identity-detectable replaced target settles as `target-drift`;
  the executor retains the external bytes and creates no recorder call or
  `PublishedCopyEvidence`.
- Normal first-pass execution performs no additional stat. Only an exceptional
  resumed post-publication attempt pays one additional target metadata read.
- This remains ordinary concurrent-drift detection. Byte readback, adversarial
  path locking, same-size pre-cache substitution on identity-weak profiles, and
  mutation after the guard remain outside the accepted threat model.

Focused executor, feature, architecture, bug, README changelog, and handoff
documentation now describe that exact scope and performance boundary.

## Verification

- Six injected replacement cases pass across COPY, UPDATE, and MOVE_UPDATE,
  covering failures before and after the post-publish stat is cached; a seventh
  case proves repairable mtime drift resumes without recopy.
- Complete executor module: `164 passed`.
- Complete test suite: `893 passed in 48.14s`.
- Import linter: `8 kept, 0 broken`.
- Independent adversarial re-review: no remaining commit blocker.
- `git diff --check` is clean.

## Immediate Next Context

The other defects from the same adversarial review remain outside this change.
The highest-impact next candidates are preserving degraded recording in the
delivered cancel-after-publish terminal and validating retained UPDATE backup
identity during cancellation settlement. Do not expand the retry guard into
full target hashing or handle-based exclusion unless the product threat model
is explicitly changed first.
