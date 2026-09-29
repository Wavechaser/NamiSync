# Latest session — ACL fixture cleanup and target consolidation

2026-09-29, `milestone1-adelbert`, starting clean at `d444a6a`.
The user requested removal of inaccessible witness/test fixtures and explicitly
reauthorized the previously blocked target-check consolidation. Direct writes
and the native NORMAL→ARCHIVE own-effect issue remain outside this follow-up.

## Cleanup and corrected performance context

The witness cleanup had restored protected ACLs granting only the sandbox
account, which still prevented the user's account from listing fixtures.
Restored inherited ACLs under four exact task-owned roots, preserved three
original witness receipts by SHA-256, then removed 6,173 fixture entries.
Reparse fixtures were unlinked without traversing their targets. The removed
roots are `handle-acl-witness/`, `review-fallback-temp-74ce6dada1464d8f93be45367fb82225/`
and `differential/result1-neighborhood-temp/` plus `result1-neighborhood-native-temp/`
under `build/executor-simplification-20260929/`. Native-user reads confirmed
the preserved receipts are accessible. Original logs, scripts, differential
captures and benchmark source/reports remain.

Cleanup manifests and original ACLs are retained in `differential/acl-fixture-*`.
The witness receipts now live at `differential/handle-acl-<original-id>-receipt.json`;
`acl-fixture-cleanup.json` maps original paths and exact hashes to the new paths.

The user reported F: contention during the earlier finishing benchmarks and
provided rerun medians of 3.150 / 1.640 / 0.373 / 0.297 / 1.956 seconds across
the five bands. PERFORMANCE records the supplied comparison table. Earlier
contended endpoints do not establish a regression. These user-reported values
are separate from this follow-up's candidate measurement.

## Target-check remainder

M1_PLAN records the reopened bounded outcome. The minimal patch was accepted
on retry: fresh COPY/MOVE_UPDATE reuse preparation's final target-fidelity
check; retained continuations still recheck. Final target-root admission,
prepared-temp proof, MOVE_UPDATE old-target/trash proofs, UPDATE, durability
and recording remain unchanged. Existing native/retry seams passed 45 tests
before the edit. Candidate tests, oracle trace classification and broader gates
are in progress; no mergeable implementation commit has been made yet.

Evidence remains under `build/executor-simplification-20260929/`; new gate
receipts use `differential/target-*`. The saved `b1b58476` differential capture
remains the starting behavior comparison; the task-created baseline worktree
is archived and need not be restored. Preserve the unrelated `b8baf42d`
root-admission worktree, original F: benchmark source and historical evidence.
Native ACL gates use the actual user and standard external pytest temp.
