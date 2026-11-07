# Latest session — bounded admission behind idle GC, 2026-11-08

## Outcome and scope

On base `2d256012`, the user approved a small five-second admission-wait guard
while renderer collection is pending. Lifecycle uses one monotonic deadline
across spurious wakeups. Expiry refuses admission before creating a session;
service, registry failure reconstruction and bridge preserve the dedicated
`maintenance_pending` category. Existing task-start error surfaces display
“Renderer maintenance is still pending. Retry or restart NamiSync.”

The reservation remains until actual GC completion or renderer exit. The native
collector and original release/close handler still wait; this change does not
cancel GC, allow collection during execution or promise a five-second total
command response. Pending transport observation may start before the refusal
arrives, but the definitive response settles it without automatic resubmission.
Provisional start state is cleaned up and fresh requests can succeed after GC.

No renderer recovery, new collection trigger, phase-transition collection,
heap cap or verification pipeline is added. Verification pipelining and small-file
batching remain M2. Prior post-Close findings remain in PERFORMANCE.

## Verification and evidence

Evidence is in `build/gc-admission-timeout-20261108/`. It retains baseline,
focused, browser, integrated-registry and department receipts, failed test
attempts, findings and independent review. The final interfaces department passes
all 2,261 cases. Independent review approves the final code/tests and confirms
all 14 changed product/test files match their recorded hashes. Local documentation
target and diff checks pass.

Review caught two propagation omissions before delivery: the registry's closed
failure mapping and page-specific fallback messages. Both are direct consumers
of this same new refusal. Corrections preserve existing generic-failure behavior.
The first 2,260-case interface pass predates those corrections and is not final
integrated acceptance. Initial test-only expectation/import errors remain in
raw logs and are not passing evidence.

No live app, measuring-session artifact or study fixture was touched. No
branch/worktree was created. No native renderer behavior changed or release
package was rebuilt. Ignored evidence is retained for review and resumption.

## Prior context

Copy-path consolidation is committed as `2d256012`, with evidence in
`build/path-consolidation-20261107/`. Verification Follow and the older
exact-receipts checker repair remain `323b5377` and `1d1917c3`, with evidence in
`build/verify-follow-20261107/`. Their subject records remain authoritative.
