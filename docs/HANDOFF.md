# Latest session — trace the execution review receipt failure, 2026-11-06

The installed default-window execution review failed its final `exact` host
check twice in 12 interleaved runs at `b2e872e6` and twice in 12 at
`6745868d`. All four preserved driver reports showed matching detail and
window operation IDs and revision 26 at failure reporting. The browser
retention/actions passed. The earlier larger-window case also reported
`["exact-receipts"]`. These reports establish the symptom across revisions
and sizes. The missing host condition in those runs is unknown.

- Paired trials and the four failure directories: `build/receipt-rate-20261106/`.
- Earlier larger-window receipt: `build/scale-headroom-20261106/larger-completion-checks.json`.
- Original default failures, isolated private-desktop pass and four passing
  diagnostic reruns: `build/copy-plan-read-opt/`. Small-file findings and
  remaining M2 batching scope are in [PERFORMANCE](PERFORMANCE.md) and
  [M1_PLAN](M1_PLAN.md).

The headed test now records which host conditions failed in the same
evaluation that rejects completion. On recurrence retain the scenario
evidence directory. [TESTS](TESTS.md#execution-review-completion-trace)
describes the trace. One specific hypothesis is a partial Inventory window:
the producer attaches integrity items only for the returned row IDs, while
the test compares the latest window's item count with the entire fixture.
The four prior diagnostic reruns each saw 24 rows and 24 items. An actual
failed trace is needed to attribute the intermittent failure.

All 26 nonheaded cases in the execution review module passed using pytest's
normal temp location. Two earlier runs with workspace temp directories timed
out during the composition test's initial Plan drain, before tracing. A
controlled mismatch exercised the real failure writer; its sample is in
`build/receipt-trace-unit-complete/test_execution_review_phase_ac0/completion-receipt-trace.json`.

The concurrent resource and stability study owns its app and workload.
Both headed sizes were deselected for this change. For an attended diagnostic
after the study, use an available input desktop to match the original
reproducer. This command selects the default case and gives its evidence a
fresh location under the system temp directory. Routine unattended journeys
use the private desktop described in [TESTS](TESTS.md#running-installed-journeys).

```powershell
$receiptRoot = Join-Path $env:TEMP ("namisync-review-" + [guid]::NewGuid().ToString("N"))
.\.venv\Scripts\python.exe -m pytest -q -o "addopts=" -m headed --basetemp $receiptRoot "tests/interfaces/web/test_task_execution_review_headed.py::test_installed_task_execution_review_real_copy_and_capture[default]"
```
