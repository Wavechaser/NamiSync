# Latest session — verification Follow and receipt repair, 2026-11-07

## Integration in progress

The user approved the installed execution receipt correction, separate commits
for it and the Verify Follow fix on milestone1, and removal of the recovery
branch after accounting. The test-only correction is ready for its atomic commit.
The independently reviewed Follow fix is still preserved at recovery commit
`0ac426f6` on `codex/wip-20261107-verify-follow`, based on `bcb7978f`.
Do not merge/cherry-pick that recovery commit as-is.

The receipt checker now verifies exact displayed-row/result membership and
independently verifies all fixture paths from the immutable retained result at
ordinary release, before Close. Both checks bind request/session identity.
Lifecycle ordering, command/control receipts and production behavior are unchanged.

## Verification and immediate next step

Evidence lives in `build/verify-follow-20261107/`. The combined reviewed
candidate passed 2,255 interface checks in `interfaces-final.xml`; two
subsequently added duplicate controls are included in the 40 passing focused
checks in `receipt-focused-final.xml`. The standalone test correction also
passed all 40 focused cases on milestone1 before restoring Follow, recorded in
`receipt-base-integration.xml`. Both installed execution sizes passed in
`headed-final.xml`; their native evidence is in `headed-passed/`.
The prior installed Inventory pass remains valid: its product and driver did
not change. Independent review approved the test correction and the Follow
fix independently. No full release packaging is claimed.

The old false failures and causal/durable proofs remain in `headed-initial/`
and `review/window-receipt-*`. Both failed runs actually verified all 24 files;
the checker incorrectly compared partial pages of 14/17 with 24.

Next reconstruct only the reviewed Follow product/tests/subject docs from the
recovery commit, condense its register and update this handoff, verify exact
candidate identity and review, then commit separately. Confirm all recovery
changes are integrated or superseded before deleting its branch. The saved
resume-register amendment is in `resumed-register.md`. No unrelated dirty
work was present. Prior performance/release obligations remain in their owners.
