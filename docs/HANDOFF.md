# Latest session handoff

## M1-7: Plan fixture repaired; full measurements fail budgets (2026-09-16)

Base `1c14ccc` on `codex/wip-20260914-1600-m1-7`. The user authorized the
confirmed Plan runtime-error fix, a single 1.5-second comparison after acceptance,
and a full measurement only on pass, with a stop afterward. That sequence is
complete. Preserve this pass separately; do not amend earlier commits, merge to
`milestone1`, prune recovery history or begin another fix/run.

### Confirmed cause and correction

The retained driver record showed committed selection and running execution,
with the dialog already closed while the page still awaited transient closing.
The headed fixture polled `data-closing`, although production promises no minimum
closing duration. Both confirmation paths now arm paused, effect-free finite
animations before trusted input and finish them only after native closing
witnesses. The live page waits on the durable native acknowledgment. Production
admission, modal/inert behavior and zero-motion timing are unchanged. The fix
changes only the headed child and its owner guard, plus documentation.

### Verification and measurements

- Independent source review passed; focused tests 50 passed / 1 deselected.
- Interfaces suite: 1,667 passed, one pending-artifact skip, 3,507 deselected.
- Installed Plan GUI: 1 passed / 2 deselected in 41.50 s. One launch was rejected
  before process creation due to approval-review model capacity; the unchanged
  launch succeeded on retry. This was not a failed test or a test rerun.
- All 38 source/wheel/installed product files match. Previous 5,140-test ordinary,
  12-import-contract and generic-tree GUI evidence remains applicable because
  product bytes and those seams are unchanged.
- All 21 untimed component readiness cases passed. One changed-search comparison
  (5 fresh processes / 30 samples) passed: p95 151,705,000 ns, max 153,806,600 ns.
- Compact authority froze successfully. Full readiness passed 35 cases across
  15 processes. One full run completed 175 children / 775 samples / 35 metrics.
- Terminal validation rejects fixed budgets: 27 metrics pass and 8 fail. Six
  changed-sort p95 values are 1.629–1.861 s (limit 1.5 s; all maxima below 3 s).
  Retained memory is 443,437,056 bytes (422.895 MiB), limit 320 MiB. Execution-start
  receipt p95/max are 283/284.1 ms, limits 100/250 ms. The compact memory case
  measures expanded retained review state, so old projection-only numbers are
  not a directly equivalent baseline.

### Preserved evidence and next discussion

Evidence root: `build/m1-7/evidence/plan-ack-fix-20260916/`. It contains the prior
confirmation-driver record, passed functional logs, installed byte identity,
`views/comparison.json`, full readiness/collection/child receipts, an arithmetic
summary, and preservation records. The complete versioned authority and raw
measurement files are `tests/interfaces/web/m1_7_plan_compact_authority.json`
and `m1_7_plan_compact_measurements.json`; old protected evidence is untouched.
The installed environment remains under
`C:/Users/Spectrum/AppData/Local/Temp/namisync-plan-ack-fix-20260916-headed/`.

Stop for discussion of the remaining budget failures. No post-run diagnosis,
optimization or measurement rerun is authorized by these results. Legacy
compatibility remains confined to historical evidence reading. `cf5a00b`, the
separate `30d35f3` fix and earlier recovery commits remain intact;
`milestone1` remains `40ca76f` and M1-7 stays unmerged.
