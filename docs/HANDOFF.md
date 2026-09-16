# Latest session handoff

## M1-7 P6: fixture corrected; focused round complete (2026-09-16)

Base `28c7b44` on `codex/wip-20260914-1600-m1-7`. The user authorized fixing
the cancellation-drain failure and running focused measurements. The fix and
remaining selection-retention checks are complete. One focused measurement
round completed; seven of eight metrics pass. Stop here before more optimization,
measurements, a full run or integration. Budgets remain unchanged.

### Confirmed cause and correction

The busy-close test required the very next 0.1-second drain to contain the
canceling event. Dispatcher publishes that event before returning, but the
SessionObserver hands it to the adapter asynchronously. The exercised test and
cancel/delivery/publication code match `353092b`; earlier passes depended on
scheduling rather than a same-batch guarantee. The test now gates the actual
canceling offer, proves Dispatcher can be CANCELING before adapter delivery,
then releases and waits for completed delivery before requiring exactly one
event. Earlier running updates remain permitted in the intervening batch.
Repeated close must remain pending, the task retained and no duplicate event
returned. This is a test-only correction, with no sleep or timeout increase.

Service tests now verify projection membership shares the exact retained
workflow decision initially and after mutation; full selected/excluded
populations, exclusion details and destructive/byte facts remain consistent;
preview DTOs are fresh; and close releases the state-owned decision. No product
files changed during this resumption. P6 production remains in `28c7b44`.

### Verification

- Corrected cancellation case: 1 passed; busy-close neighborhood: 2 passed.
- Selection-retention focused targets: 4 passed; whole owner file: 36 passed.
- Independent source review: no findings; all prior retention gaps closed.
- Ordinary suite: 5,152 passed, 5 skipped, 30 deselected in 260.57 s.
- Import contracts: 12 kept, zero broken.
- Fresh installed Plan GUI: 1 passed, 2 deselected in 44.26 s.
- Untimed readiness: 23 cases across three fresh processes passed.

Initial test-development logs retain a gated-batch assertion that also needed
to permit an earlier RUNNING event and two incomplete test-fixture values; these
were corrected before the passing owner/ordinary gates. Driver review also
caught its unused five-sample memory/p95 mismatch before measurement. The driver
now uses maximum for memory, and records/verifies its own hash. No measurement
was restarted or retried.

### Focused results

Each timing metric uses five fresh processes and 30 samples; memory uses five
fresh cold processes and five samples. Forty measurement processes completed
215 samples. Sort p95/max limits remain 1.5/3 seconds; memory 320 MiB; receipt
p95/max 100/250 milliseconds.

| Metric | p95 | Maximum | Result |
| --- | ---: | ---: | --- |
| Filename ascending | 0.728396 s | 0.732044 s | Pass |
| Filename descending | 0.737502 s | 0.741012 s | Pass |
| Size ascending | 0.751273 s | 0.769985 s | Pass |
| Size descending | 0.728179 s | 0.751456 s | Pass |
| Mtime ascending | 0.746687 s | 0.750556 s | Pass |
| Mtime descending | 0.746219 s | 0.756561 s | Pass |
| Review memory overlap | — | 266.785156 MiB | Pass |
| Execution-start receipt | 170 ms | 175.4 ms | p95 fails |

Memory fell from 422.894531 MiB to 266.785156 MiB, leaving 53.214844 MiB below
320 MiB; no criterion revision is needed. Receipt p95 fell from 283 to 170 ms
but remains 70 ms above its budget. This run provides no phase attribution for
the remaining receipt cost. Do not infer a particular next fix from total time.
These are focused diagnostic comparisons, not a replacement for full M1-7
terminal acceptance. No full 35-metric run was launched.

### Evidence and preserved state

Evidence root: `build/m1-7/evidence/p6-resume-20260916/`. It contains raw
focused/ordinary/import/installed logs, source comparison, the one-shot driver
and scripts. `comparison/` holds fresh source/installed/wheel/runtime authority,
all readiness and measurement receipts with hashes, incremental status,
per-child dispersion and final `comparison.json`.
Independent `comparison/evidence-audit.json` verifies all 43 unique processes,
215 samples and receipt/invocation/log hashes, plus all 42 declared source files,
38 installed/wheel members and 14 runtime roles against the frozen authority.
The fresh installed environment remains under
`C:/Users/Spectrum/AppData/Local/Temp/namisync-p6-resume-20260916-headed/`.

The original P6 stop/evidence remains under
`build/m1-7/evidence/p6-budget-20260916/`; previous full results remain under
`build/m1-7/evidence/plan-ack-fix-20260916/` and in the unchanged versioned
compact files. Historical evidence compatibility stays reader-only.
Keep `cf5a00b`, `30d35f3`, `28c7b44` and prior recovery history unchanged.
`milestone1` remains `40ca76f`; M1-7 stays unmerged. Discuss the remaining
receipt p95 before further work.
