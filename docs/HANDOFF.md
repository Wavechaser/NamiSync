# Session Handoff

Status (2026-09-02): LC-0b corrected the LS-1 guard and the lifecycle register
is ready to resume at LC-1a. The earlier stop was procedurally valid, but its
product-defect classification was withdrawn: no normative contract promises
globally monotonic raw synthetic-`Gap` arrival across recovery.

## LC-0b outcome

- `DISPATCHER.md`, `INTERFACES.md`, `HISTORY.md`, and `M1_BRIDGE.md` specify
  recovery from the last accepted non-`Gap` producer cursor. Existing required
  browser witnesses intentionally accept a repeated synthetic Gap sequence.
- `test_ls_1_delivery_has_no_silent_loss_or_duplicate` now barrier-forces a
  64-slot stream ejection, holds terminalization until recovery subscription
  and retained-tail delivery, excludes Gap marker values from producer-event
  uniqueness, and accounts for every missing reliable producer sequence using
  a finite announced recovery interval.
- A companion self-test proves duplicate reliable delivery and unannounced
  reliable loss fail the detector. Terminal event/record uniqueness and
  terminal-last remain separate exact assertions.
- The unsupported `Post-ejection replay cursor regression` entry was deleted
  from `BUGS.md`, not marked fixed. Production, `event_bus.py`, T1 artifacts,
  department entries, capacities, and event behavior are unchanged.
- This repository's `TASK_LIFECYCLE_SIMPLIFICATION.md` is now the sole active
  plan. The older `.codex` copy is intentionally no longer maintained.

## Verification

- Corrected lifecycle guard module: `19 passed`.
- Final deterministic LS-1 detector: 30/30 fresh-process passes.
- Frozen T1 oracle: exact baseline match at SHA-256
  `AC08426E682BC362CC9E0CAB9A7ABE4FA998518DC5E9CCFD3FB0DF86F68CB53B`.
- Ordinary suite with bundled Node: `4909 passed, 4 skipped, 28 deselected`.
  The preceding run without Node had only the five required-runtime failures.
- Import law: 11 contracts kept, zero broken.

## LC-1a recovery

Recovery commit `dc94aef` on
`codex/wip-20260902-0633-task-lifecycle-lc1a` is approximately partial work,
not a review unit. Keep it until the rebuilt checkpoint passes, but never merge
or cherry-pick it. Create a fresh LC-1a branch from the corrected guard
baseline and use only `git diff 197a2fc dc94aef -- <path>` as recovery input.
Review and reintroduce each path at the intensity fixed in the active register.

Discard and rebuild the WIP diffs for `tests/test_task_lifecycle.py` and
`tests/test_bridge_service.py`. Retain the task port and strong indirect import
contract inside LC-1a. Retain command stripes only if exact single-flight and
disjoint-command concurrency tests prove them. Commit the complete LC-1a
outcome atomically after its full gate; do not begin LC-2 before that commit.
