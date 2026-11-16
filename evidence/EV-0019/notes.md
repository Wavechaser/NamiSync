Notes for "Inventory row envelope proof and correction (2026-10-05)": text files chosen from `build/gui-followup-20261005`, `build/gui-inventory-refinement-20261005/`, verbatim, each under an H1 naming its source path. Non-Markdown files are fenced. JSON is in `data.json`.

# `build/gui-inventory-refinement-20261005/README.md`

# GUI Inventory refinement evidence

Owned by this task from milestone1 at 614cd19. Preserve user-handoff.md verbatim.
Use c1–c5 prefixes for outcome evidence; unique run identifiers never overwrite
failed receipts. Scripts, fixtures, logs, source hashes and review bindings stay
here, outside tracked production. No cleanup of earlier task evidence. M1_PLAN
owns current scope; HANDOFF owns immediate resumption; this directory owns run
chronology. Delete task-owned temporary fixtures only after their evidence has
been retained and all processes have exited.

C5 installations use fresh `c5-install-<phase>-<run>/` directories. Each contains
source staging, wheel, venv, install/build logs, exact package identity and pinned
runtime dependencies. Never instrument earlier acceptance installations. Keep
baseline and candidate installations separate; preserve hashes, restoration
receipts and measurements before considering temporary runtime cleanup.

# `build/gui-inventory-refinement-20261005/c1-recovery.md`

# C1 recovery accounting

- Original checkout/ref: milestone1 at 614cd194e35d0cde2aee2e2aa9ccdd0f5a167935.
- Recovery branch: codex/wip-20261005-2356-inventory-windows.
- Recovery commit: a638040cf8976b2b08264e38065b2358edc7bf04.
- Integration: none. milestone1 remains at the original base; no push or PR.
- Population: exact 25 task-owned files in preserve-c1.ps1 and the commit diff.
  C1 product/tests/docs are preserved; C2 is design only; C3–C5 have no product
  edits. No unrelated dirty files existed except the directly relevant user
  HANDOFF, whose original bytes remain in user-handoff.md with the recorded hash.
- Evidence: c1-review.md and binding JSON, c1-focused-01*, c1-ordinary-01*,
  c1-native-01*, c1-native-inventory-02*, and c1-envelope-proof.*.
- Readiness: 370 focused, 5,921 ordinary and 12 import contracts passed. Four
  ordinary Windows privilege skips; six installed gallery/shell cases passed.
  Installed Inventory failed twice before input at wait-foreground. No gate
  waived; no actionable source-review findings. Not merge-ready.
- Resume: obtain verified foreground for the installed Inventory journey, rerun
  it against matching frozen product/producer/checker/driver bytes, refresh
  invalidated evidence only, and renew independent review binding. Reconstruct
  a coherent C1 commit on milestone1; never merge/cherry-pick this WIP as-is.
  Then continue C2 target, C3 menus, C4 table, C5 measurements in recorded order.
- Cleanup: no task worktree; test processes exited through harness containment.
  Retain test temporary roots because they contain the raw installed receipts.
  Retain this recovery ref until integration and complete accounting.

# `build/gui-inventory-refinement-20261005/c1-review.md`

# GUI-C1 independent review

Reviewer: `/root/c1_envelope_review`, fresh no-history GPT-6.1 Sol/high agent,
read-only. Base 614cd194e35d0cde2aee2e2aa9ccdd0f5a167935; candidate hashes and raw
receipts are recorded in c1-review-binding.json.

Final verdict: no actionable issues in source, tests, contracts or final docs.
The complete analytical bounds include row fields, execution overlays, global
metadata and JSON escaping: Inventory 1,193,678 bytes, Plan 2,395,485 bytes,
against unchanged 8,388,608-byte admission. Valid production bridge witnesses
remain distinct from conservative impossible-all-fields upper-bound fixtures.

Reviewer independently inspected raw logs/manifests: 370 focused, 5,921 ordinary,
12 import contracts and six installed gallery/shell checks passed. The four
ordinary skips are Windows symlink/reparse privilege error 1314. Product, tests
and drivers match frozen evidence; final differences are delivery documentation.
Root corrected the BRIDGE command table's omitted snapshot field and reviewer
rechecked that correction and all matching component documentation.

Not merge-ready: both installed Inventory attempts failed at wait-foreground
before product assertions. Preserve failed receipts; no product failure or
successful native journey is inferred. Resume the required foreground-owned
Inventory check, refresh changed dependencies and renew review binding before
reconstructing a coherent C1 commit. Recovery WIP is never merge/cherry-pick input.

# `build/gui-inventory-refinement-20261005/c5-baseline-summary.md`

# C5a frozen baseline, 2026-10-07

Base `455fd49`; the working-tree diagnostic inputs are bound by the adjacent
before/after manifests. Product wheel and installed identity were revalidated
before and after each collection. Reports: `c5-baseline-plan-01.json` and
`c5-baseline-inventory-01.json`. Representatives Plan05 and Inventory01 are
excluded from the samples. All six fresh children completed 16 observations.
No ordinary suite ran concurrently with these collections.

First identity-correct target coverage, milliseconds, median [minimum, maximum]:

| Gesture | Plan | Inventory |
| --- | --- | --- |
| Initial (3) | 112.9 [110.8, 137.7] | 99.3 [97.2, 101.1] |
| Sequential edge (9) | 103.0 [83.0, 140.5] | 83.5 [78.4, 87.4] |
| Jump (9) | 80.8 [75.6, 105.2] | 76.2 [72.5, 83.3] |
| Covered return (9) | 16.5 [14.2, 16.6] | 16.6 [8.8, 16.7] |
| Burst (9) | 192.9 [180.1, 199.4] | 413.8 [396.1, 435.1] |
| Keyboard (9) | 158.6 [151.2, 162.2] | 72.2 [67.3, 74.6] |

Per-child coverage medians, same gesture order:

| Component / PID | Initial | Sequential | Jump | Return | Burst | Keyboard |
| --- | --- | --- | --- | --- | --- | --- |
| Plan / 29772 | 110.8 | 86.3 | 81.0 | 16.6 | 194.6 | 159.3 |
| Plan / 11892 | 137.7 | 106.0 | 80.6 | 16.5 | 189.8 | 155.4 |
| Plan / 37660 | 112.9 | 85.6 | 80.4 | 16.5 | 194.2 | 158.6 |
| Inventory / 17216 | 99.3 | 86.5 | 80.5 | 16.6 | 424.1 | 72.6 |
| Inventory / 44424 | 97.2 | 78.8 | 74.7 | 16.6 | 413.8 | 71.1 |
| Inventory / 44236 | 101.1 | 80.5 | 76.2 | 16.5 | 397.0 | 69.2 |

Plan's nine bursts dispatched 27 reads, maximum concurrency one, discarding18.
Inventory dispatched72, maximum concurrency eight, discarding63. Covered returns
show coverage while a discarded read remains pending; their separate settlement
times are not substituted for visibility. Plan keyboard has two adopted window
reads per gesture; Inventory has one. Raw reports retain all phase counts and
per-child/combined summaries, including setup requests excluded from aggregates.

Jump request medians (nine per component), milliseconds, nested spans unsummed:

| Phase | Plan | Inventory |
| --- | --- | --- |
| Browser round trip | 53.9 | 49.0 |
| Registry outer | 1.4172 | 1.9090 |
| Inner window build | 1.3030 | 1.8991 |
| Bridge capture | 43.2905 | 37.2865 |
| Bridge projection | 3.1687 | 3.5501 |
| Native JSON encoding | 0.6005 | 0.6150 |
| Browser validation | 0.7 | 0.9 |
| Adopted DOM | 5.9 | 21.7 |

Jump canonical-budget/native-wrapper/callback-script median bytes:
Plan198624/215696/215780; Inventory176388/194671/194755.
Registry outer time does not substantially exceed inner work; the conditional
lock follow-up is not triggered. Do not assign the unobserved round-trip remainder
to a specific queue. Instrumentation overhead is not calibrated. These values
diagnose this instrumented profile; they are not production latency guarantees.

Windows11 build26200, i7-13700K,63.69GiB RAM, F:SN850X NVMe; Python3.13.14,
pywebview6.2.1, pythonnet3.1.0, WebView2 154.0.4258.53. All children:1267x764,
DPR1.75, Light, normal motion, hidden Details,24px rows; Plan viewport853x359,
Inventory880x321. Power and unrelated workload are unverified. Startup and
projection construction excluded. Synthetic DOM gestures are not native input
acceptance. Compositor presentation and host thread/lock queues unobserved.

Conclusion: proceed with the accepted Inventory viewport coalescing, preserving
action-owned reads and rerun the identical matrix. Further optimizations remain
conditional on the post-coalescing observations.

# `build/gui-inventory-refinement-20261005/c5-fixture-review.md`

# Approved fixture correction

2026-10-07, fresh reviewer /root/c5_fixture_review, base6c6e10f.
No unresolved findings. Seven-file candidate approved; collector files excluded.

Real case variants, same parents/stats, unchanged complete manifest facts except
fingerprint/digest, and actual published-window browser admission were inspected.
Historical authorities unchanged. Negative missing-prior witness stays strict.
Evidence: 68 focused, 5924 ordinary/four privilege skips, 12 imports and Plan04
16-observation installed compatibility proof with restored assets. Ordinary01
remains failed; unchanged ordinary02 passed with the correct Windows identity.

SHA-256 bindings:
- CHANGELOG.md: 319C70BEFD03508762E7623B503E2E7ED6B3419C110E9887B577F403A6D53A19
- docs/HANDOFF.md: 76DFFB3D4D787637046807028C8D75F832747774B2F5C8D0A1B12DC16ADA99D3
- docs/M1_PLAN.md: 5438F1D2AD36317D91A8F3F2D794053239DD4B6370BFCAAD17A203A072219448
- docs/PERFORMANCE.md: 496008BC07CB086ACA3D24616207782E4B39C1531420B042ACDCCCBC192CFFCA
- tools/performance/plan.py: 570159F4ACC522A03B800B7EB1D79D23228B4DA077BDBDBEF33651DFD42729DA
- tests/interfaces/web/test_plan_review_scale.py: C87EADC8500AAEAF8D2A7D504010BC43A89ED7A4AA7617FD05EF4B155F7291C0
- tests/interfaces/web/test_m1_8_execution_receipt_scale.py: F05AD7CF17A7DF4C666C3E49214373690D6468D1CED9E2D07680EC25A71ADD2E

# `build/gui-inventory-refinement-20261005/c5-helper-review.md`

# C5 helper consumer repair review

Independent reviewer: /root/c5_method_review. Base: 3c984b6.
Approved five paths; other pending C5 changes excluded. No findings.

The bounded display expectation matches production. Full destination hashing,
prior-group identity and rootless geometry remain. New real service/registry
publication witness closes the fake-only contract gap.

Evidence: c5-helper-focused-03 (53 checks, 12 import contracts),
c5-helper-interfaces-01 (1952 checks), c5-representative-plan-02 reaches actual
page evaluation after successful helper settlement and then fails only the new
collector startup handshake. Before/after installed identity and restoration pass.

Frozen SHA-256:
- tools/performance/execution_receipt.py: 569B183727F5D5015EBB295D3709EB778DD7C35BB92E3BE9B826D080A8B8AFE0
- tests/interfaces/web/test_m1_8_execution_receipt_scale.py: ECC61762D29A8C5EF365644D356AA0826589F5F083B24F78B739E48D136DB38B
- docs/M1_PLAN.md: B98E3C069ECB158D0DB7C13DCA385E99CBFC4FB074B9FAC1C001A35096AF643F
- docs/HANDOFF.md: 7F47FA9F797BF2F6AB2AC8E5EA72F83135D35C0DA7E07FF0D1B40E19B6373D1D
- CHANGELOG.md: F46E68781795847A4561B2D7B5972299C3DD340AE1098C147DDFD0D59D29274F

# `build/gui-inventory-refinement-20261005/c5-method-review.md`

# C5a independent review and integration

Reviewer `/root/c5_method_review`, fresh read-only context, base455fd49.
Inspected actual method, frozen controls, two representatives, all six baseline
children/raw receipts and final ten-path staged diff. Independently recomputed
every per-child/aggregate phase/gesture/byte/DOM count, median and range; verified
exact host/browser request correlation, landing, asset hashes/restoration and
source/wheel/installation identities. No final finding.

Review corrections completed before measurement: truthful incomplete errors,
actual bridge settlement rejection, first visible frames independent of pending
reads, separate final settlement, request-count-aware phase summaries, repeatable
keyboard reset with component-correct buffer placement and visible active target.
Focused06:29 passes; ordinary01:5953 passes,4 WinError1314 privilege skips,
35 headed deselected; imports12 kept. Reviewer compared296 executable inputs
against baseline and ordinary manifests; no change. Documentation-only result
updates were excluded from executable dependency comparison.

Atomic integration: `61ee878`, `test(tools): measure installed table loading phases`.
No recovery WIP merged or cherry-picked. Candidate/coalescing work follows separately.

# `build/gui-inventory-refinement-20261005/c5-recurrence-review.md`

# C5 fixture recurrence review

No fixture repair authorized/applied at this record. AGENTS recurrence question
sent to user after finite investigation; no product validator relaxation proposed.

Builder /root/c5_loading_design and independent /root/c5_method_review inspected
actual production planner, projection and bridge admission plus the shared scale
fixture, execution receipt/UI adapters, C5 driver and direct controls.

Two stale fixture contracts met the same actual publication-to-browser seam:
the old unbounded move label (corrected in 6c6e10f), then synthetic RECASE rows
without prior path. The unchanged browser rejects 36 rows in the actual first
window, all canonical recase/rename with prior_name null. The execution summary
validates. Earlier estimate 41 is superseded by the retained Node output.

Proposal: swap only kinds at indices3/12 (NOOP/RECASE), preserving numeric sort
witnesses and counts; add same-parent uppercase previous leaf and source stat
to all RECASE operations. Production planner supplies prior path/stat when an
actual leaf case changes. No attempt to make this scale fixture executable.

Read-only c5-inspect-fixture-swap.json and its producer script were independently
reviewed. Base120000/119968 and heavy240000/239968 projection/visible populations,
16667 RECASE each, zero missing or unchanged prior paths. Only artifact digest
and plan fingerprint differ in complete manifests; counts/depth/siblings/raw
sort/scalar/kind/selection facts remain identical. Historical timing authorities
must stay unchanged. New C5 measurements start only after correction approval,
focused/department/ordinary/installed seam gates and fresh review.

Raw failures, restored assets and exact install identity evidence remain.
No baseline or optimization result is accepted. Final pending work and decision
belong to docs/M1_PLAN.md and docs/HANDOFF.md, not this chronology.
