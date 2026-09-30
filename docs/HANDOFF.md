# Latest session — direct target writes

2026-09-30, `milestone1-adelbert`, implementation base `b9c4ad3`. The user's
blanket 8 MiB threshold is implemented across device types, with no volume/model
discrimination. M1_PLAN owns result 8's scope and decisions; EXECUTOR owns the
mechanism and PERFORMANCE owns measurements. No further refactor is active.

## Changes

- `b9c4ad3` restricts held-root delegation to concrete NativeFileSystem.
  Subclasses keep runtime admission; no public resolve contract change.
- Direct target writes keep the invocation-owned handle through aligned writes,
  exact EOF, metadata, flush and publication. The pipeline recycles aligned
  backing buffers only after hash/write completion, within 32 MiB including
  alignment slack, and releases storage on exit even with retained exceptions.
- Remote roots, unknown geometry and direct-open refusal fall back to buffered
  writes with opt-in diagnostics. Later write or EOF errors fail the copy.
  Source reads stay buffered. Temp creation precedes leftover recovery; eligible
  single-chunk buffered copies use a synchronous path confirmed by actual EOF.

## Verification and evidence

Evidence remains under `build/executor-simplification-20260929/`.
Native tests ran as the actual user with default pytest temp. Alignment/tail,
late-write/EOF-failure, delayed hashing/writing, failure cleanup and real
copy→ledger→verifier controls pass. The first broad neighborhood's three obsolete
test controls were migrated (readinto observation/injection and metrics shape).
Final ordinary receipt `differential/result8-ordinary-final.log` contains 5,720
passes, four capability skips, 34 deselections and one stale cleanup-count
assertion. Its one-line correction passes all 95 audit tests in
`result8-audit-tests-final.log`; independent review accepts reuse of unaffected
ordinary evidence. This was not a single all-green ordinary invocation.

All 12 import contracts and the 70-row/344-effect guard scan pass. The three-run
custom oracle candidate is independently classified: 43 rows change only the
declared temp trace and matching timeline, 27 remain identical, and all other
facts match. The immutable 67-group differential's four differences contain only
seven obsolete cleanup-count errors; the classification receipt preserves the
original driver/audit and all effects, trees and settlement fields.
The official committed-baseline check follows the atomic implementation/re-pin
commit; its terminal receipt is `differential/result8-oracle-official.log`.

All 25 production copies/readbacks pass with stable source and physical
product/tools/tests/driver hashes, expected write modes, no fallbacks, bounded
allocation and zero final reservations. Measurement prefix:
`measurements/result8-b9c4ad3e-20260930-201114-989e90d9`.
Five-band medians are 2.789 / 1.474 / 0.351 / 0.129 / 0.909 s. Small files reach
1.40 MiB/s, below the 1.6 MiB/s goal; 4 GiB reaches 4,505 MiB/s. The comparison
is sequential and repeated-source; it is not a causal or other-device claim.
Independent source and evidence review found no unresolved substantive issue.

## Preservation

Failed and non-acceptance attempts remain with
`differential/result8-early-attempt-disposition.txt`. The invalid workspace-temp
native fixture was removed by its sandbox owner after actual-user enumeration
was denied; `result8-invalid-fixture-cleanup.json` retains exact file hashes.
No ACL widening was required. Original F benchmark sources and the unrelated
detached `b8baf42d` worktree remain untouched. No task worktree or recovery branch
was created for result 8; earlier task recovery refs were already accounted.

Previous accepted commits: `d43f832` (version recognition), `6157226` (path
composition), `878f15e` (single-path dispatch), `2f1511f` (threshold evidence).
The earlier device-specific threshold candidates remain historical diagnostics;
the user-selected 8 MiB policy supersedes them for shipping behavior.
