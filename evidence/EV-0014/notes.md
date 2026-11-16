Notes for "DOM mutation cost follow-up (2026-11-09)": text files chosen from `build/dom-costs-20261109/`, verbatim, each under an H1 naming its source path. Non-Markdown files are fenced. JSON is in `data.json`.

# `build/dom-costs-20261109/measurement/README.md`

# DOM native diagnostics — 2026-11-09

This ignored evidence directory owns only this task's frozen source copies,
profiles, target fixtures, drivers and receipts. Do not remove or modify the
read-only reused source corpus or other measurement sessions' resources.

`manifest.json` binds Git `fb448fac` baseline, each complete frozen candidate,
the source corpus (10,000 × 32 B files, 100 folders), helper bytes, runtime and
host facts. `fixtures.jsonl` registers every owned target before creation and
identifies the reused source owner. `trees/` holds full package snapshots;
`runs/runs/` holds raw events, 1 s passive process samples, CDP heap observations,
logs, result receipts and independent audit copies; `runs/profiles/` holds fresh
per-run application data. Evidence and owned fixtures are retained for review.

Use `probe.py prepare` once, `freeze_candidate.py` after the final builder source is
settled, then `probe.py run NAME` in the original declared order below. The final
schedule is amended by [schedule-amendment.json](schedule-amendment.json): four
pre-idle Plan runs are conservatively excluded after the user's external-load
report, and two quiet opposite-order pairs replace their comparison. All ten
main-run results are retained in [final-summary.md](final-summary.md).

1. baseline-plan-01
2. candidate-plan-01
3. candidate-plan-02
4. baseline-plan-02
5. baseline-inventory-01
6. candidate-inventory-01

Plan runs copy plus linked Verify; Inventory runs Baseline, Verify and Rebaseline.
Each run uses a fresh Job, profile and (for Plan) target inside this directory.
No forced GC, heap cap, cadence, drain or custody changes are introduced by the
driver. Existing element/listener counters apply equally to each arm. Inputs,
outputs, helpers, runtime and source metadata are checked after normal Close.

Run the corresponding `audit_plan.py NAME` or `audit_inventory.py NAME` only
after `result.json` exists. These copy closed databases, audit exact populations
and outcomes, and verify original database hashes remain unchanged. `report.py`
aggregates only complete runs with verified audits and one browser identity.

Native timing runs must not overlap the task's heavy tests or other task-owned
native runs. Existing unrelated measuring resources are not controlled. ABBA
Plan pairs address ordering/host drift only weakly; all timings, CPU and memory
observations remain diagnostics, not product budgets or stable speed claims.

# `build/dom-costs-20261109/measurement/collection/README.md`

# Clean collection and ACK CPU diagnostic

This separate experiment uses one frozen post-DOM package for a 25 ms then
200 ms collection pair. Only the test wrapper changes the existing clean-result
linger constant at runtime; no shipped source, custody, ACK behavior, pull-loop
or paint cadence changes. Profiles, targets, Jobs and receipts are separate
from the main DOM comparison and retained for review.

`threads.py` classifies the installed pywebview call-thread closure into ACK,
completion ACK, event drain, window, anchor, detail and other buckets without
retaining request payloads. CPU spans the original Thread.run, including handler,
response serialization and native return. It excludes thread creation on another
thread and final thread teardown. Summed wall time overlaps and is not critical
path time. `check_helper.py` checks classifier cases and the installed closure
shape; runtime source hashes are also frozen in the manifest.

After the main candidate is frozen, run `probe.py prepare`, then
`probe.py run linger25-plan-01` and `probe.py run linger200-plan-01`, exclusively
from the task's other native runs/heavy tests. Use `audit_plan.py NAME` after
each completed run and `report.py` for resource aggregation. Source/mirror,
metadata, producer/runtime checks and normal empty-Job Close remain required.

One ordered pair is diagnostic, with no claim of stable elapsed-time improvement.
It investigates whether fewer calls reduce CPU and where the remaining time is
spent; it does not approve the latency or custody contract changes.

# `build/dom-costs-20261109/measurement/collection/final-summary.md`

# 25/200 ms collection and ACK attribution

Two fresh owned native Plan runs use the identical frozen post-DOM 303-file
package, fixture, producer, runtime and instrumentation. Only the diagnostic
wrapper sets the existing clean-result linger constant to 0.025 or 0.2 seconds.
No production source, ACK/custody protocol, pull-loop, GC, row limit or paint
cadence is changed. Both runs started after the user-reported idle boundary and
ran without this task's other native/heavy tests. This is one ordered pair,
not a stable speed or latency acceptance claim.

Both runs pass exact mirror, source hashes/metadata, source/runtime/helper
identities and independent closed-database audits, with normal exit0 and empty
Jobs. All classified command bucket counts match the independent host-handler
counts. There are zero unclassified bridge calls. `ack-summary.json` binds
results, audits, raw thread samples, aggregation, manifest and checker hashes.

## Execution phase (copy plus linked Verify)

| Metric | 25 ms | 200 ms |
| --- | ---: | ---: |
| Elapsed seconds | 113.447 | 112.176 |
| Host CPU seconds | 80.344 | 69.813 |
| Renderer CPU seconds | 31.953 | 32.000 |
| GPU CPU seconds | 12.266 | 13.469 |
| Drain commands | 3207 | 562 |
| Plan window commands | 218 | 215 |

The larger window cuts drains 82.5% and host CPU 13.1%, but saves only 1.271
seconds in this pair. Rendering and full-window traffic are essentially unchanged.

## Whole application lifetime call-thread attribution

CPU spans the original pywebview call-thread body, including handler,
serialization and native return. It excludes caller-side thread creation and
final thread teardown. Startup, planning and close are included in this table;
the execution-only resource values above are separate.

| Bucket | 25 ms calls | 25 ms CPU s | 200 ms calls | 200 ms CPU s |
| --- | ---: | ---: | ---: | ---: |
| Ordinary ACK | 3523 | 1.453 | 876 | 0.250 |
| Completion ACK | 6 | 0.000 | 6 | 0.000 |
| Event drain | 3214 | 5.438 | 569 | 3.469 |
| Window | 220 | 4.641 | 217 | 4.500 |
| Anchor | 64 | 0.047 | 66 | 0.047 |
| Other commands | 25 | 0.688 | 24 | 0.703 |
| All bridge call threads | 7052 | 12.266 | 1758 | 8.969 |

Call-thread count falls 75.1%, while measured call-body CPU falls only 26.9%.
The same reliable results still need representation/validation/serialization;
window calls are unchanged and account for about half the remaining measured
call-body CPU. The session-worker whole-lifetime CPU is nearly unchanged,
58.906→58.234 s, as are audit/observer responsibilities (audit CPU 4.125→4.438 s,
observer 1.203→1.203 s). Whole host CPU is 88.984→78.203 s.

This supports the earlier finding: reducing bridge traffic saves resource work,
but much of that work overlaps the existing execution path and does not remove
the underlying file/durable work or renderer cost. It does not prove an exact
critical-path decomposition or attribute all unmeasured host savings to thread
creation. Summed thread wall times overlap and must not be added to elapsed time.

ACKs are roughly half the calls, but only 1.453 s of measured call-body CPU at
25 ms. This is neither predicted savings nor a complete upper bound: piggyback
or batching must still perform custody cleanup in another call, while omitted
caller-side thread-creation cost may also shrink. A reduced-ACK contract should
be judged as a bounded transport/custody redesign with its own evidence, not as
an expectation of halving execution time. The latency and custody decisions
remain deferred for user discussion.

The classifier reads only the installed closure's function/argument identity
and a bounded canonical request prefix, retains no payload, and aggregates fixed
buckets. Its 11 focused helper cases and installed source shape pass. The final
checker confirms the frozen bridge request places command before payload and
within the 256-character classifier prefix. Ended-only aggregates avoid live/ended
double counting; no exact per-phase thread CPU claim is made. Native CPU sampling
has 1 s boundary uncertainty and Windows thread-time accounting has finite resolution.

# `build/dom-costs-20261109/measurement/final-summary.md`

# DOM native comparison

Baseline is exact Git `fb448fac`; candidate is the settled 303-file package
frozen in `candidate-identity.json`. Four files differ logically: app.js,
plan_review.js, table_controller.js and tree.js. Twenty-seven additional raw
differences are Windows checkout/archive newline differences. Both whole-package
hash maps, prior baseline manifest, helpers and runtime identities are retained.

The corpus is the prior registered read-only 10k × 32 B source in 100 folders.
Every run uses a fresh owned profile/Job and each Plan run a fresh owned target
inside this evidence directory. Same producer and 1 s passive sampler apply to
all arms; no execution GC, heap cap, row-limit, cadence or bridge changes occur.
All ten runs pass exact source hashes/metadata, runtime/helper/product hashes,
normal close with exit0/empty Job, and independent closed-database population
audits. Plan also passes exact mirror checks. Original database files remain
unchanged by the audits. All native timing was exclusive from this task's heavy
tests and other native runs.

The user reported external machine activity during approximately the preceding
fifteen minutes. The four pre-idle Plan runs are conservatively excluded;
this does not establish that each was affected throughout.
`schedule-amendment.json` records the idle receipt boundary at 2026-11-09
03:47:34 UTC (11:47:34 Asia/Shanghai). baseline-plan-01/02 and candidate-plan-01/02
are retained and audited but excluded from performance conclusions.

## Quiet Plan comparisons

One candidate03→baseline03 pair was followed by a bounded opposite-order
baseline04→candidate04 pair because the first quiet comparison was unfavorable.

| Pair | Arm | Seconds | Renderer CPU s | GPU CPU s | Host CPU s | Windows | Drains | Created elements | Renderer peak MiB |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 03 | baseline | 128.161 | 40.484 | 16.141 | 96.734 | 247 | 3502 | 217334 | 689.43 |
| 03 | candidate | 137.564 | 46.625 | 18.563 | 103.984 | 265 | 3658 | 220805 | 731.77 |
| 04 | baseline | 117.828 | 33.438 | 14.672 | 83.922 | 227 | 3299 | 212000 | 683.25 |
| 04 | candidate | 112.242 | 31.875 | 13.875 | 78.922 | 217 | 3205 | 209659 | 663.72 |

The unfavorable first quiet result did not repeat with reversed order. Both
arms drift substantially downward with time; these observations establish
neither a stable throughput/CPU gain nor a repeatable regression. The deterministic
DOM mutation and geometry probes are separate evidence of removed redundant
operations. Aggregate renderer native time is not all attributable to detach
and insertion work.

Plan measurements cover combined copy plus linked verification; the driver has
no exact monotonic phase boundary for separate copy/verification CPU attribution.

## Quiet Inventory pair

| Mode | Arm | Seconds | Renderer CPU s | GPU CPU s | Host CPU s | Windows | Drains | Created elements | Renderer peak MiB |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline | baseline | 26.346 | 10.250 | 4.594 | 25.906 | 55 | 694 | 93178 | 307.38 |
| Baseline | candidate | 25.962 | 8.266 | 3.750 | 26.188 | 52 | 690 | 91219 | 285.64 |
| Verify | baseline | 25.490 | 8.500 | 3.172 | 26.406 | 52 | 677 | 84539 | 342.62 |
| Verify | candidate | 25.419 | 7.422 | 1.859 | 25.094 | 53 | 668 | 87552 | 311.74 |
| Rebaseline | baseline | 25.512 | 6.172 | 2.281 | 24.844 | 57 | 669 | 99093 | 332.19 |
| Rebaseline | candidate | 25.515 | 8.922 | 4.047 | 26.750 | 54 | 675 | 95153 | 315.06 |

Elapsed time is effectively unchanged; renderer CPU is mixed by mode and sums
24.922→24.609 s. Sampled peaks are lower in this one pair; no stable memory or
leak claim follows. CPU uses complete 1 s samples grouped by process identity,
so boundaries have sampling uncertainty. User-reported idle is not complete
host isolation.

`summary.json` retains raw aggregation for all ten runs, including excluded
observations; `report-*.log`, per-run `result.json` and `audit.json` retain
chronology, identities and exact checks. The separate `collection/` experiment
uses its own helpers and must not be merged into the DOM A/B comparison.

# `build/dom-costs-20261109/review/final-review.md`

# Final independent review — approved

Approve the coherent `perf(interfaces): reduce redundant table rendering`
checkpoint against base `fb448fac04bef3f7b360122d8f48ec5ef2a3ab5d`.
The final population is four product files, five focused probes and five owning/
delivery documents. No remaining actionable defect or unmet named gate found.

The source/functional review and two correction dispositions remain in
`source-review.md`, `geometry-review.md` and `source-gates-identity.json`.
Final recheck confirms all nine product/test hashes unchanged; product bytes
match native02 wheel staging and independently frozen corrected witness source.
Functional gates are2289 interface passes and all6 affected installed journeys.
Native assertions/helpers were not weakened; negative controls reached intended
assertions and failed. Diff whitespace checks pass. Root's documentation checker
reports179 local file links checked. No tests or native work were repeated
during the final timing runs.

Main measurement review independently rederived durations, element/listener
counts, per-process-identity CPU deltas and renderer peaks across all ten DOM
runs; both303-file packages and raw receipt/audit hashes match
(`measurement-review-check.json`). All data/source/close checks and closed-db
population audits pass. The four pre-idle Plan observations remain excluded,
using the recorded03:47:34UTC user-reported boundary. Quiet opposite-order Plan
pairs reverse apparent benefit, so final docs claim no stable CPU/speed gain or
regression. Inventory lower sampled peaks remain qualified as one-pair evidence.

ACK attribution review inspected `threads.py`, installed pywebview `_call`, the
wrapper, helper checker, independent handler counters and aggregation source.
Classification uses the real closure identity and bounded command-before-payload
prefix. Ended-only bucket snapshots avoid prior double counting. Independent
recalculation reconciles every command bucket, thread totals, CPU totals, sampled
execution CPU and all helper/manifest/result/audit/thread hashes
(`ack-review-check.json`). Both separate collection runs pass exact audits and
normal empty-Job close. Whole-lifetime ordinary ACK CPU is1.453125s/3523calls
versus0.25s/876calls; bridge totals7052/12.265625s versus1758/8.96875s.

Final PERFORMANCE, HANDOFF, M1_PLAN, PRESENTATION and CHANGELOG agree with
the implementation and raw evidence. They distinguish whole-lifetime call-body
attribution from sampled execution CPU, exclude caller-side thread creation,
retain required cleanup costs, qualify the single ordered collection pair, and
make no proportional critical-path or stable speed claim. Test-only200ms linger
and future ACK piggybacking remain discussion-only; production25ms collection,
ACK custody,250/500ms paint/read cadence, GC and domain behavior remain intact.
No unsupported latency guarantee or protocol authorization was introduced.

Evidence, profiles and task-owned fixtures are deliberately retained. No new
worktree/branch requires cleanup. Final task delivery should include the actual
commit identity once created; this approval applies to the reviewed unchanged
product/test hashes and final documentation delta.

# `build/dom-costs-20261109/review/geometry-review.md`

# Geometry review — 2026-11-09

Frozen baseline `fb448fac`; candidate package hashes in `candidate-identity.json`.
The candidate includes the positive-height cache and zero/unknown fallback.
Production Plan panel/CSS uses gallery-derived 256-row fixtures, total1000.
No bridge/domain mutations were submitted. All native windows/profiles belong
to these bounded Job-contained runs.

The linked Verify switch hypothesis was disproved in this fixture: hiding the
source/settings controls left the viewport height unchanged. Candidate03 and
the initial portions of later runs show no extra coverage request.

The finite actual resize witness uses Win32 SetWindowPos on the owned host to
grow its height120px. A one-shot resize event applies a near-loaded-edge Follow
before ResizeObserver delivery. This deliberately controls the ordering; it
does not measure how frequently an ordinary app timer encounters that order.

| Receipt | Before/after clientHeight | Immediate/final scrollTop | Extra request |
| --- | --- | --- | --- |
| geometry-candidate-05.json | 405/525 | 5762.857/5762.857 | offset208 |
| geometry-baseline-01.json | 405/525 | 5642.857/5642.857 | none |
| geometry-corrected-01.json | 405/525 | 5762.857/5642.857 | none |

Loaded rows end at6144px. After subtracting the24px sticky header the candidate
reveals about120px outside loaded coverage and asks for another window; the
baseline clamps within coverage. This is a bounded cache-validity regression,
not data loss, false success, or a timing/memory guarantee. Both normal-close
receipts report exit0 and no remaining PIDs. The independently frozen corrected
candidate (`corrected-identity.json`) restores the baseline final landing during
the existing frame, without an uncovered-window request, and closes exit0 with
no remaining PIDs. It deliberately retains cached immediate placement before
that frame; the witness does not assert synchronous pixel equality.

Smallest general candidate correction: retain only the latest passive Follow
offset through the already-scheduled viewport reconciliation frame, use that
frame's existing fresh measurement to re-clamp before coverage admission, then
retire it. Manual/keyboard/other programmatic scroll ownership must cancel the
pending offset; hidden/reset/dispose paths must not resurrect it. This avoids
maintaining a caller-specific list of every possible header/status/Details or
window size change. Builder and parent own implementation and focused tests.

Retained unsuccessful attempts: candidate01 could not open its own localhost
DevTools socket (WinError10013 sandbox restriction); normal-close receipt has
exit1 and no remaining PIDs. Candidate02 used an incorrect probe selector and
failed before the measurement; it closed exit0 with no remaining PIDs. Candidate04
establishes the same size-change math via component style and is supplementary,
not the actual-window evidence. The subsequent native runs used normal Windows
permissions. Scenario files retain witness expressions; source trees are frozen.

# `build/dom-costs-20261109/review/source-review.md`

# Independent source and functional gate review — 2026-11-09

Provisional source/functional approval, pending final matched diagnostics and
delivery documentation. Base `fb448fac04bef3f7b360122d8f48ec5ef2a3ab5d`.
`source-gates-identity.json` independently binds the final four product files and
five changed probes to builder identities; all product bytes also match native02
wheel staging and the independently frozen corrected native resize witness.

Reviewed the complete product/test diff, owning M1 row and PRESENTATION contract,
earlier failed native receipts, baseline-negative and correction-negative probes,
and corrected installed/department receipts. No remaining actionable defect found.

- In-place row publication retains only the current window. Compatible overlap
  stays attached; current handlers, dynamic cells and focus ownership survive.
  Structural Plan publication restores scroll before existing focus/keyboard
  reveal. No new row cache or unbounded work was introduced.
- Passive Follow measurement is cached; hidden reentry remeasures. The existing
  frame corrects positive stale geometry before coverage reads, and input,
  publication and lifecycle ownership retire that correction. Independent native
  baseline/candidate/corrected witness establishes the correction's seam.
- Dispatch-only ticks skip unchanged paint; accepted responses and new local
  progress paint independently. First, urgent and explicit paths retain the
  default forced paint and original250/500ms scheduling.
- Two introduced findings were corrected: cache validity and temporary row
  publication extent collapse. The four first-native failures are manifestations
  of the latter; fresh PlanAgain task creation succeeded. No third defect or
  second separately fixed instance of the same mechanism was established.
- Existing native helpers/assertions remain unchanged. Added fake mutation
  behavior represents transient scroll clamping; full and sparse-overlap
  tests fail on the earlier candidate and pass corrected code. Baseline-negative
  controls hit all five intended DOM/geometry/paint assertions.
- XML and logs independently confirm2289 interface passes, no skips/errors/
  failures,4237 deselected; all6 affected installed journeys pass. `git diff
  --check` passes. No native/test work was launched during timing measurement.

Bridge/collection investigation numbers were reproduced from raw out5 receipts
using the original report/phase scripts and checked against transport source.
It discloses live/ended worker double counting, sample-window differences and
unmeasured causal attribution. ACK piggybacking remains discussion-only; no
bridge, drain, GC, custody, domain or cadence implementation was changed.

Final commit readiness additionally requires completed matched diagnostics,
accurate limits/results, final HANDOFF/M1 status and coherent delivery docs.
