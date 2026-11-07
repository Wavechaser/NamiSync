# Latest session — verification Follow and receipt repair, 2026-11-07

## Delivered changes

The user authorized two separate commits on milestone1 and recovery-branch
cleanup. Test correction `1d1917c3` checks exact displayed Inventory row/result
membership and independently verifies all fixture paths from the retained
ordinary result at release. Both bind task/request/session identity. Missing,
extra, duplicate, substituted and wrong-identity controls preserve full coverage.

The accompanying Follow commit reconstructs the independently reviewed recovery
payload `0ac426f6`, never merging its WIP history. Snapshot v3 adds one reliable
latest integrity-item identity alongside the execution cursor. Automatic and
ordinary Verify/baseline/rebaseline follow fast files omitted from active progress.
One automatic read finishes while newer targets coalesce. Cached Go retires a
competing request and exact ownership fences late success/error callbacks.
Existing cadence, manual overrides and Gap/session/view guards remain.

Enabled ordinary Follow can land on its final item in the same session/view.
Linked Verify still retires navigation at terminal and opens Inventory at release,
without cross-pane ID mapping or delayed release. Domain events, sync/hash/ledger
policy, resource budgets and release packaging are unchanged.

## Verification and accounting

Evidence root: `build/verify-follow-20261107/`.

- `interfaces-final.xml`: 2,255 interface cases passed. The two final duplicate
  controls passed with all 40 focused cases in `receipt-focused-final.xml`,
  giving passing evidence for all 2,257 distinct cases.
- `receipt-base-integration.xml`: the test correction independently passes all
  40 cases on milestone1 before restoring Follow.
- `headed-final.xml`: both installed execution window sizes pass with the
  corrected checker. Native evidence is copied in `headed-passed/`.
  The prior installed Inventory pass in `headed.xml` is unaffected.
- `follow-integration.xml`: 510 direct consumer checks pass after reconstruction.
- `integration-identity.json`: all 306 package-source files exactly match the
  tested candidate. Git also confirms the recovered product, tests and subject
  docs equal their reviewed recovery versions; delivery docs supersede paused
  records and the test correction is independently additive.
- Independent reviewers approved the Follow and receipt outcomes separately.
  Review reverse controls are in `review/follow-retirement.*`.
  No unrelated changes or test-oracle weakening were included.

The original receipt failures and diagnostic/durable proofs remain in
`headed-initial/` and `review/window-receipt-*`. Both runs verified all 24
files. Their latest pages held 14/17 results at offsets 10/7; the old checker
incorrectly demanded 24 in one page. That cause is resolved by the test commit.
Earlier restricted Temp and workspace-basetemp failures remain retained in
initial logs and were corrected by using the normal Windows Temp route.

The recovery payload is accounted for in the two coherent commits. The WIP ref
`codex/wip-20261107-verify-follow` is disposable after their integration and
final accounting. No push or full release package is part of this delivery.
Prior performance/release obligations remain in their owning documents.
