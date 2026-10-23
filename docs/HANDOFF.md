# Latest session — Known-missing Inventory notices, 2026-10-24

User-authorized narrow follow-up on `milestone1`, starting at `b243bb71`.
M1-12, release, DOC-2, push and PR remain inactive.

Both Inventory refresh and preliminary integrity scans filter published
DISAPPEARED notices against the ledger after normal recording. A named row
must be missing and have a scope token different from this scan. Files and
folders use the same rule. Newly missing rows and unknown subjects retain
notices; incomplete-scan reconciliation is unchanged. Original scanner
results and diagnostics are untouched. No core/db or GUI contract changed.

The initial broader reconciliation proposal was superseded by the user's
narrower instruction. Its historical evidence and disposition are retained in
`build/target-absence-20261024/reconciliation-design-01.md`.

Verification: 210 focused workflow/runtime/Inventory review checks passed;
then the added incomplete-present-row check passed in the 184-case workflow
neighborhood run. The complete workflow department passed 954 tests. All 12
import contracts passed. The complete interface department passed 2,092 tests.
Receipts are in `build/target-absence-20261024/`. Fresh independent review accepted
the implementation without findings; root owns the final commit and clean-tree
check. No headed check was required for this workflow-only publication change.

Initial reproducer failed at repeated notice publication for refresh/Verify.
The Baseline test fixture initially emitted a Verify-phase result; corrected
that test-only construction before acceptance. No product failure was inferred
from that fixture error. No recovery refs, stashes or unrelated files changed.
