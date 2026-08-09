# NamiSync Session Handoff

Date: 2026-08-09
Branch: `milestone1`

## Session Outcome

Closed the two remaining executor H3/H4 integrity gaps without changing the
reviewed full-intent/safe-selection contract or adding steady-state filesystem
probes.

- UPDATE now flushes prior recorder work before all final backup, prepared-temp,
  source, and live-target validation. COPY, UPDATE, and MOVE_UPDATE bind the
  already-observed post-publish kind/size and available stable identity to the
  prepared temp before attestation.
- MOVE, RECASE, TRASH, DELETE, MKDIR, and readonly clearing retain a lightweight
  process-local mutation attempt through recording or failure settlement.
  Confirmed, ambiguous, or unreadable durable state degrades recording without
  inventing success evidence; exact unchanged pre-state remains recording-OK.
- Retry, pause, and cancel preserve mutation-attempt truth. Durable cancellation
  uses `canceled-after-mutation`; created and resumed directory metadata is
  finalized/restored during cancel and failure-probed when restoration errors.
- Failure-only probes report current durable state even after a mutation syscall
  returned, and MOVE/TRASH require both an exact retained source and absent
  destination before classifying an attempt as unchanged.

## Verification

- Focused H3/H4 regression gate: `27 passed`.
- Complete executor suite: `213 passed`.
- Complete pytest suite: `1241 passed, 1 skipped in 110.98s`. The skip is the
  existing privilege-dependent directory-symlink substitution test.
- Import linter: `8 kept, 0 broken` across 50 files and 189 dependencies.
- Two independent implementation reviews found three H4 edge cases; all three
  were fixed and the final re-review found no remaining code blocker.

## Immediate Next Context

- The demonstrated UPDATE recorder-flush temp substitution is closed without an
  extra success-path stat. A stable-identity inode substitution after the final
  temp guard is also rejected using the cached post-publish observation.
- Identity-weak same-kind/same-size substitution and same-object byte mutation
  that preserves observed metadata remain outside the external-writer contract.
  Full closure requires a handle-bound publication protocol or a byte reread;
  the latter would materially reduce small-file throughput and was not added.
- `_published_target_durable_state` remains a strict four-value invariant. Both
  producers are exhaustive today, so its `RuntimeError` is unreachable through
  legitimate settlement; extending that vocabulary requires updating the
  mapping and its call-site containment together.
