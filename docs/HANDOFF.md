# Latest session — GUI alignment

2026-10-05 on `milestone1`, base `999a568`. The user ratified seven
GUI units in [M1_PLAN](M1_PLAN.md): A1–A5 complete; execution-to-Verify
navigation (A6) deferred to M1-10; all previous-location/rename redesign
(A7) deferred to a focused session. Standalone Verify remains on Integrity
with Sync disabled. No A7 presentation-boundary exception was approved.

## Integrated work

- A1 `4f314b2`: visible recovery after an incoherent move-reveal window and
  conflict scrolling.
- A2 `498eb24`: first-visible column snapshot lets only Filename absorb
  enlargement, preserving bounded manual resizing.
- A3 `49801f7`: shared counted Filter menu and pinned Regular icons.
- A4 `4a39789`: optional full-height right details column with independent
  task/item card scrollers and capped shrinking details/task-rail widths.
- A5, this closing commit: aligned standalone Inventory surfaces, status Refresh,
  semantic labels, five columns and optional Details. Bounded stored-baseline
  checksum and shared column sizing preserve scan/evidence truth, tree ownership,
  action scopes and Plan's Notes donor. Direct consumers and component docs migrated.

## Verification and evidence

Evidence lives in `build/gui-alignment-20261005/`; `a1-review.md` through
`a5-review.md` own independent review decisions, and `integration.md` records
commit identities. The final A5 gate passed 5,887 ordinary tests with four
Windows symlink-privilege skips, all 12 import contracts, and all seven installed
Inventory/gallery/task-shell cases. It also passed 23 early real-service cases,
84 focused consumers and 12 token checks. The ordinary run includes the primary
interfaces population and closes batch integration.

Final identities are `a5-frozen-03.json` and `a5-source-binding-03.json`;
receipts are `a5-native-final-03.xml`, `a5-integration-final.xml` and
`a5-imports-final.log`. Failed/superseded receipts remain. The user ratified
the combined correction of inherited CSS alignment; final geometry checks
column edges and scroll ownership. A duplicate dimension literal now consumes
its existing token. Native foreground failures stopped before input and were
resolved by selecting the test window; the replacement-Details fixture was
migrated without weakening hit/ownership checks. Evidence owns the chronology.

## Immediate operational context

No active GUI batch unit remains. A6 stays with M1-10; A7 needs the user's
future focused session. No new domain/integrity action, push or PR was added.
No task worktrees or branches were created. Exact external test roots and raw
evidence are retained; `a3-temp-ownership.json`, `a4-temp-ownership.json` and
`a5-temp-accounting.json` record ownership and exclusions. No scratch deletion
was attempted; unclaimed or access-limited roots remain excluded from cleanup.
