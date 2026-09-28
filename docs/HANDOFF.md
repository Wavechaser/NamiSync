# Latest session — executor correctness follow-up

2026-09-28, `milestone1-adelbert`, starting clean at `30b0c2c8`.
M1_PLAN owns the two approved atomic outcomes.

## Scope and current work

The user reported a preexisting unreadable-junction admission escape and fragile
fast-path selection under method-wrapping instrumentation. The reported escape
was classified for a separate fix, not deferred. A clean mandatory stop was
reported, then the user explicitly approved both corrective outcomes.

1. Verified fix: executor descendant walks stop only on FileNotFoundError; other
   observation errors propagate. Native resolve and both trash-destination
   consumers retain all normal-path guards. Native ACL regressions assert
   refusal only, restore permissions and remove the junction before fixture
   cleanup. EXECUTOR and BUGS document the corrected behavior and limits of
   evidence; no full GUI-path reproduction is claimed.
2. Pending the fix commit: a combined default-production held-root regression
   asserts zero physical resolutions and zero leaf-volume probes after root
   admission. Keep method-identity fallback behavior and document why method-
   wrapping profilers exercise fallback. No capability-flag contract change.

Further runtime admission/throughput work stays paused. The earlier runtime
scope choice is not resolved by this correctness approval.

## Verification

Fix gates pass: 468 focused, 574 direct (two skips), 5,583 ordinary (four skips,
34 headed exclusions), 12 imports, settlement 30 × three, guard scan
70 rows/391 effects/zero missing admissions and all 67 unchanged differential
groups. The approved ACL behavior change has its own held/unheld native red
and passing witnesses. Four frozen files and full-gate dependency hashes match.
An initial fixture cleanup failure is retained; exact inspection confirmed
no remaining deny ACEs or junctions and unchanged owned sibling markers.
The corrected parent-first teardown passed before final gates.
Independent review: `executor/independent-review-descendant-refusal-20260928.md`.

## Evidence and preservation

Original user reports are retained in
`build/executor-review-20260928-30b0c2c8/`; do not rerun the write-through probe.
New correction receipts live under
`build/root-admission-optimization-20260928/executor/descendant-refusal-*` and
`build/root-admission-optimization-20260928/resume/executor-descendant-refusal-*`.
Existing baseline equivalence fixtures
remain unchanged; only the explicitly approved unavailable-descendant refusal
may differ from the old behavior.

The preceding performance outcome at `30b0c2c8` passed 5,579 ordinary tests and
67 differential groups and measured 3.387 seconds / 1.153 MiB/s on 1,000 × 4 KiB.
Those are historical measurements, not a new measurement of this correction.
Preserve the clean `b8baf42d` comparison worktree, original F: corpus, prior
raw/failed receipts and historical recovery refs. No unrelated work is included.
