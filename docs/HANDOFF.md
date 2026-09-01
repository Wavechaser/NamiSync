# Session Handoff

Status (2026-09-02): the task-lifecycle simplification register is stopped in
LC-1a on a verified preexisting LS-1 delivered-event ordering defect. The
mergeable guard commits are `755600c` (LC-0) and `197a2fc` (LC-0a). Incomplete
LC-1a work is preserved only on recovery commit `dc94aef` at branch
`codex/wip-20260902-0633-task-lifecycle-lc1a`; it is not a review unit and must
not be merged or cherry-picked.

## Closed guard work

- `docs/TASK_LIFECYCLE_SIMPLIFICATION.md` owns the active closed register and
  `docs/TASK_LIFECYCLE_TEST_LEDGER.md` owns the finite removal-test census.
- T1 remains frozen at SHA-256
  `AC08426E682BC362CC9E0CAB9A7ABE4FA998518DC5E9CCFD3FB0DF86F68CB53B`.
- LC-0a added repeated generated-ID identity coverage, an exact LC-6
  department-entry disposition, corpus-format freeze governance, and the
  temporary/permanent guard-cost decision without changing production.

## Stop finding

- The LC-1a form of
  `test_ls_1_delivery_has_no_silent_loss_or_duplicate` failed intermittently:
  one of ten isolated reruns delivered sequence prefix
  `[1, 2, 3, 68, 4, 141, ...]`.
- An untouched clone at `197a2fc` then failed the unchanged frozen detector on
  its first isolated run with the identical prefix. The defect is therefore
  preexisting, not an LC-1a regression.
- The supported mechanism is stream ejection followed by observer replay: the
  ejection `Gap` carries a later envelope sequence, but observer recovery
  resumes from `first_missed_seq` and can synthesize a lower-sequenced replay
  `Gap`. `docs/BUGS.md` records this as open `Post-ejection replay cursor
  regression`.
- The frozen T1 corpus still matches because its complete plan session does not
  force bounded-subscriber ejection and replay. No persistence or filesystem
  drift was observed.

## Incomplete recovery snapshot

- The snapshot contains the uncommitted LC-1a application lifecycle/port,
  service and web-drain migration, import boundary, partial documentation/test
  ledger, reanchored host and lifecycle tests, and a partially migrated
  `tests/test_bridge_service.py`.
- It is intentionally not merge-ready: bridge/service/web test migration,
  structural call-surface proof, lifecycle aggregate reduction, full
  documentation, adversarial review, and broad verification remain incomplete.
- Evidence before the stop included an unchanged T1 check, 12 pure lifecycle
  owner tests, 14 service positive-owner cases, 13 LS-4 cases, 74 host cases,
  and 12 kept import contracts. The full lifecycle module later exposed LS-1;
  the ordinary LC-1a suite was not run. Earlier bridge-service migration had
  17 failures and one teardown error before its latest partial reanchoring.

## Next safe action

Obtain explicit adjudication for the preexisting LS-1 defect. Either fix it as
a separate, focused commit from clean `197a2fc` with a permanent regression, or
explicitly accept the boundary defect and authorize resumption. Only then
rebuild useful recovery-snapshot changes into a coherent LC-1a commit and run
its full register verification. Do not begin LC-2 through LC-6, and do not
merge or cherry-pick either lifecycle recovery commit.
