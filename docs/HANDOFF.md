# NamiSync Session Handoff

Date: 2026-08-08
Branch: `milestone1`

## Session Outcome

Implemented the selected MEDIUM findings from the M1 core-logic audit and
recorded the remaining deferred boundaries as release gates.

- M6 now uses one logical/native Windows path contract from service admission
  through workflow validation, managed-root containment, scanner, preflight,
  executor, verifier, and inventory binding. Persisted and displayed paths stay
  unprefixed; native calls receive extended spelling; ambiguous or device roots
  are refused; native filenames are removed from user-facing diagnostics.
- M3/M15 now use reset-only history v5 receipt windows. Exact semantic
  duplicates retain full, non-counting receipts; one supported oversized event
  retains a bounded hash-only receipt, degrades audit, and does not discard the
  later stream or terminal truth. Broken ordering, identity, context, or storage
  still fails the prefix.
- History receipt metadata/order, item identity/semantics, immutable item
  projections, lifecycle/watermark/count projections, and terminal truth are
  authenticated. Strict `WITHOUT ROWID` event storage and append/finality
  guards prevent replacement or reopening; physical-tail checks reject rows
  outside committed watermarks. Bounded identity indexes preserve oversize
  conflict detection, and event pages validate session attribution.
- M14 frozen-resume and stale integrity selection now read only canonical,
  location-owned inventory row IDs in bounded snapshot chunks. Explicit path
  selection remains bounded and full Verify All remains intentionally O(n).
- Deferred M1/M2/M4/M7/M11/M12 and post-finalization observer-cleanup
  visibility are documented at their feature/release boundaries. Findings
  already fixed or rejected on contract/arithmetic grounds received no new
  production work.

## Verification

- History/schema/dispatcher/service/CLI focus: `266 passed`.
- Dispatcher regression file after explicit observer-status fixture updates:
  `53 passed`.
- Complete pytest suite: `1215 passed, 1 skipped in 44.73s`. The skip is the
  existing optional real directory-symlink substitution test on a host without
  the required privilege; deterministic guard coverage remains active.
- Million-item history gate: 1,000,000 items across 50 runs in 136.700 seconds;
  maximum window commit 121.026 ms; summary reads 1.670/1.605 seconds; item/event
  page maxima 16.256/14.818 ms; retained peak 256 events/79,360 bytes. Every
  locked threshold passed.
- Import linter: `8 kept, 0 broken` across 50 files and 189 dependencies.
- M6 focused gate: `406 passed`; its independent adversarial review was clean.
- Two independent history reviews and the final performance-delta review found
  no remaining P0-P2 defect after the receipt/schema repairs.
- M14 repository/workflow focus: `33 passed`, with the full workflow file at
  `24 passed` after noncanonical-ID and baseline/rebaseline filter coverage.

## Immediate Next Context

- The host has `LongPathsEnabled=1`; a fresh Windows process/VM with legacy
  long-path policy disabled was not available. Explicit conversion seams and
  extended-prefix end-to-end tests are the deterministic automated gate.
- Live UNC integration and long-path SQLite database files remain outside the
  current local-volume/database support boundary.
- An observer `close()` failure after durable finalization cannot rewrite live
  or retained terminal truth. It remains internal cleanup health until a future
  persistent dispatcher/store contract defines a public projection.
- Do not ship scoped deletion until disappearing scoped subtrees mark the scan
  incomplete. Define durable store failures, future-cursor gaps, and wedged
  finalize ownership before their triggering M2 surfaces land.
