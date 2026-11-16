# test-refinement-st-h: retained claim support

## Adequacy supplement — 2026-11-17

The final v4 suppressed-signal capture, distinct from the earlier paired-test
result, observed parent deadline termination, no success publication and all
observed processes dead afterward. PID values are not lasting identities and
are omitted; counts and coverage checks preserve the claim.

```json
{
 "input": "build/test-refinement/1026541/st-h/h-f2-new/capture-v4.json",
 "sha256": "7b2a27d693fef40ad79b41b161176a42741a7cf2f5c2d5f4fd657e567a627923",
 "termination_entered": true,
 "termination_returned": true,
 "observed_job_pids": 9,
 "launched_pid_in_job_at_start_and_termination": true,
 "liveness_checked_for_every_observed_pid": true,
 "all_observed_pids_dead": true,
 "wrapper_poll_after_terminate": 0,
 "error_type": "AssertionError",
 "error_message": "headed scenario exceeded its whole-scenario deadline",
 "ready_exists": false,
 "failure_exists": false,
 "final_exists": false
}
```
