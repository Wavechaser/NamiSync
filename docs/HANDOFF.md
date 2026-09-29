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
and recording remain unchanged. Development runs passed 45 prechange seams,
528 focused and 1,497 executor/workflow tests; these used default sandbox
execution and are not the native acceptance authority. The full ordinary run
explicitly requested native execution and standard external pytest temp:
5,704 passed, four skips, 34 deselected. It covers the same ordinary population.
Exact commands/results are retained in the test-tool transcript receipts.

Independent oracle review classified 21 successful absent-target stat removals
across 18 rows; the other 52 rows and all effects/settlement facts are unchanged.
The candidate three-run diagnostic, imports and fixed 67-group differential pass.
The admission scan reports 70 rows, 391 effects and zero missing admissions;
separate source review/tests verify fidelity. All 25 measurement/readback samples
passed with fixed source/dependency manifests and owned target cleanup. Final
review is pending. The default pinned oracle requires a clean committed baseline and runs
immediately after the atomic code commit.

Measurement prefix: `measurements/target-9c96893b-20260929-191353-d421178a`.
Five-band medians are 3.134 / 1.641 / 0.351 / 0.303 / 2.011 seconds; small-file
throughput is 1.247 MiB/s. Results are close to the user's separate rerun and do
not isolate an added throughput gain from the two removed checks. PERFORMANCE
retains ranges, backend/outside splits and the older contention context.

Cleanup/performance corrections are committed as `9c96893`. The four temporary
trees created by the development checks were also removed after completion;
`target-fixture-cleanup.json` records their 7,546 entries. No fixture tree from
this follow-up remains beside the evidence. Original test output is preserved.

Evidence remains under `build/executor-simplification-20260929/`; new gate
receipts use `differential/target-*`. The saved `b1b58476` differential capture
remains the starting behavior comparison; the task-created baseline worktree
is archived and need not be restored. Preserve the unrelated `b8baf42d`
root-admission worktree, original F: benchmark source and historical evidence.
Native ACL gates use the actual user and standard external pytest temp.
