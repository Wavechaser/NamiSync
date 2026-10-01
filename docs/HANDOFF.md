# Latest session — M1-9 resumed

2026-10-02. User approved resumption after mandatory stop, expanding the first
correction to the shared start-admission mechanism and narrowing the installed
witness. M1_PLAN owns the accepted details. Finish M1-9 and stop for recap/GUI
tweaks; no M1-10 or release work is authorized.

## Integration and preservation

Original/integration branch `milestone1`, current base `978ddf1`; original task
base `937af54`. Six reviewed commits have shipped: `ec3865c`, `12cae9b`,
`a84e816`, `687549a`, `9266845`, `978ddf1` (projection, timing evidence, bounded
reads, desktop reads, same-task Refresh, conditional visibility respectively).

Recovery `4b936db` remains on `codex/wip-20261001-2242-m1-9-desktop`. Never merge
or cherry-pick it as-is. Rebuild useful changes on milestone1; account for every
saved path before removing the recovery ref. No unrelated dirty work or task
worktrees exist. Ignored evidence and external fixtures remain preserved.

First atomic outcome: shared TaskStartView adoption for initial Plan/Inventory,
Plan again and subsequent Refresh hookup. Advance task mutation revision, adopt
active/unreleased identity, replace the old drain and avoid Plan-again being
misclassified as execution. Failed-list/stale-list and Plan-again probes plus
fresh independent review precede its own commit. Builder owns app.js/probes and
INTERFACES; root owns shared register/changelog/handoff.

Shared candidate is now verified: 1,890 interfaces tests pass; seven prior-red/
candidate-green production scenarios and both Refresh scratch controls pass.
Independent review confirmed the batch and trace-helper corrections. Exact
receipt: shared-ready-dept.log. The first 1,887-pass/three-anchor-failure receipt
is retained; no unresolved first-outcome finding remains.

Second outcome: reconstruct desktop action candidate atop that fix. Separate
builder owns only the two new inventory witness files. User explicitly limited
the witness to real folder-command clicks, hidden/returned missing row,
replacement shown results, screenshot and task/host Close. Use producer-owned
identity/count/display; retain original results before fallible observation,
first failure and fresh focus/hit check after manual foreground wait. Do not
implement the prior review's expanded ledger/order/bucket/helper-fault checks.
Root migrated five explicit expected command lists across the three existing
headed test files; retain all independent security assertions.

## Evidence and next gates

Evidence root `build/m1-9-20261001/`; old reviews and failed receipts retained.
Prior candidate ordinary: 5,829 passed, four skipped, 35 headed deselected;
frontend 58 passed. Existing headed: 26 passed, eight explicit command-catalog
failures. New inventory witness never passed; six failure/incomplete receipts.
Review repros `review-refresh-list-{failure,race}.{mjs,py,json}` prove false current
completed display; correcting that mechanism is now explicitly authorized.

Backend visibility neighborhood 2,785 passes, focused 795, independent 13;
imports12 and local links191 passed before final frontend work. Reuse unaffected
backend evidence; rerun affected frontend, ordinary and installed gates after
writers freeze. Package inputs must not change during wheel-backed runs.

Cold projection gate passed five fresh samples each: maxima 1.9712401/2.8123806s
under 3/6s. Current source dependency validation is in cold-evidence-current.log.
User says machine idle and authorizes further measurements if needed; none are
currently needed. User manual test-window focus is already authorized. Announce
native input intervals, verify foreground before clicks, and close the interval
when processes end. No native run is currently active.

External task evidence under C:\Users\Spectrum\AppData\Local\Temp includes
namisync-m1-9-{existing-headed,final-ordinary}-20261001 and six
NamiSync-M19-Inventory-20261001-{first,second,diagnostic,focus,manual,identity}
roots. Prior roots are indexed in build/m1-9-20261001/evidence-index.md. Preserve
receipts/screenshots/package identity before any exact task-owned cleanup.
