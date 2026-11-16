Notes for "Refresh/read cadence measurement (2026-11-08)": text files chosen from `build/cadence-measurement-20261108/`, verbatim, each under an H1 naming its source path. Non-Markdown files are fenced. JSON is in `data.json`.

# `build/cadence-measurement-20261108/README.md`

# Cadence and rendering diagnostic evidence

This task-owned ignored directory contains only source freezes, measurement
drivers, isolated profiles/targets and receipts for the November 8 cadence work.
The baseline is `39255ca30672a0d978a9e8ad423b389cbbd27244`. Product and tests are
owned by other agents; these helpers do not edit them.

- `probe.py`, `wrapper.py`: identical native producers for both variants.
- `manifest.json`, `trees/<variant>/`: frozen package, runtime and helper hashes.
- `fixtures.jsonl`: own targets plus read-only reuse of the prior owned 10k corpus.
- `runs/profiles/<run>/`, `runs/runs/<run>/`: unique data and raw native evidence.
- `audit_inventory.py`, `audit_plan.py`: independent closed-profile database-copy
  audits, retaining input hashes and leaving original databases unchanged.
- `report.py`, `summary.json`: diagnostic aggregation; scalar per-window metadata
  classifies consecutive same-offset versus shifted replies. These observations
  cannot identify every request's UI intent and do not prove strict cadence.

One fresh baseline/candidate pair per workload is planned: ordinary Inventory
Baseline→Verify→Rebaseline, and Plan copy+linked Verify. Both use 10k files of
32 bytes. Plan targets remain in this task's workspace evidence directory.
Explicit actions, terminal collection, 256-row windows and normal GC remain
production behavior. No heap cap or execution collection is injected. Counters
cover `createElement` and `addEventListener`, not all JavaScript allocations.
Host timing records retain at most 50,000 scalar records; truncation invalidates
their interpretation. Exact intervals are owned by deterministic product tests.

Interpret counts as allocation/read diagnostics and sampled peaks/times as
single observations, not release SLO, containment, leak or throughput proof.
Retain failed attempts separately. Do not delete any other session's files,
profiles or processes. No cleanup of these registered fixtures is requested.

# `build/cadence-measurement-20261108/baseline-summary.md`

# Baselines ready; candidate pending

Both source-frozen native baselines completed normally, exited 0 with empty Jobs,
and passed independent exact database-copy audits. No owned app remains open.
Baseline package is exact Git archive `39255ca30672a0d978a9e8ad423b389cbbd27244`,
303 files. Runtime, helpers, read-only corpus hashes and metadata stayed unchanged.
`producer-provenance.json` verifies the archive independently. One diagnostic
sample per workload; no stable latency/footprint or release claim is made.

| Workload phase | Seconds | Window reads | Anchor reads | Created elements | Renderer private peak MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| Inventory Baseline | 38.14 | 434 | 421 | 168,707 | 1,367.4 |
| Inventory Verify | 40.06 | 371 | 357 | 174,437 | 1,284.6 |
| Inventory Rebaseline | 41.00 | 368 | 356 | 168,380 | 1,245.9 |
| Plan copy + linked Verify | 157.98 | 320 | 64 | 361,809 | 840.1 |

Inventory shifted-window start gaps have medians 79/94/100 ms across its modes.
Plan same-offset and shifted medians are 530/544 ms. Request intent is not carried
in the backend command metadata, so these include permitted explicit/terminal
and viewport work and cannot prove a strict automatic interval.

The Inventory audit checks 10,000 exact paths/results in each mode and final
attestation state. Plan audit checks the exact 10,100 filesystem operations,
10,000 verified targets, phase history and source/target mirrors. Original
profile database bytes remain unchanged by audits.

Candidate launch is deliberately pending parent approval after product and
focused review settle. Use `freeze_candidate.py` (complete tracked plus nonignored
package population), then the same `probe.py run candidate-inventory-01` and
`probe.py run candidate-plan-01` serially. Normal local CDP access requires the
approved native execution permissions. Do not alter probe/wrapper between arms.
Run each matching audit, then `report.py` and `provenance.py`. Preserve this
baseline summary and raw artifacts when adding final comparison reporting.

# `build/cadence-measurement-20261108/comparison-summary.md`

# Cadence candidate comparison, 2026-11-08

One matched pair per workload; diagnostic evidence, not a distribution or an acceptance threshold. Baseline is exact Git archive `39255ca30672a0d978a9e8ad423b389cbbd27244`; candidate is frozen in `trees/candidate`, with full tracked plus nonignored package population and raw hashes in `manifest.json` / `identity-check.json`. Both contain 303 package files. Measurement producer and instrumentation stayed unchanged between arms. Runtime/browser identity matched. Source corpus was the prior task-owned read-only 10,000 x 32-byte fixture; profiles, Plan targets and process Jobs were task-owned.

| Workload | Seconds baseline → candidate | Window reads | Drain commands | Created elements | Renderer private peak MiB |
| --- | --- | --- | --- | --- | --- |
| Inventory Baseline | 38.135 → 54.887 | 434 → 190 | 844 → 8244 | 168707 → 133376 | 1367.41 → 761.45 |
| Inventory Verify | 40.059 → 61.366 | 371 → 218 | 713 → 8282 | 174437 → 136090 | 1284.56 → 984.89 |
| Inventory Rebaseline | 41.005 → 61.335 | 368 → 200 | 713 → 8511 | 168380 → 127255 | 1245.91 → 855.82 |
| Plan copy + linked Verify | 157.985 → 199.955 | 320 → 697 | 11634 → 11882 | 361809 → 223957 | 840.09 → 1462.60 |

Inventory candidate same-window medians were 250.70 / 250.95 / 250.75 ms; shifted-window medians were 510.57 / 511.98 / 511.02 ms. Explicit/terminal/viewport reads are included, so these classifications are diagnostics, not strict assertions about automatic intent. Deterministic tests own strict cadence behavior.

Inventory renderer sampled CPU fell from 37.58 / 37.78 / 39.36 seconds to 27.81 / 28.86 / 26.72; host sampled CPU rose from 40.83 / 42.64 / 43.36 to 76.53 / 84.86 / 86.98. Cumulative next_events handler time rose from 3.15 / 4.39 / 4.87 to 19.24 / 19.47 / 19.26 seconds. Recorded history activity duration also increased, so the slowdown is not merely terminal UI delay. Evidence supports amplified host/drain work; it does not isolate GIL, serialization or Defender effects.

Plan's requested faster loaded-window refresh changes its same-window median from 530.12 to 252.82 ms; shifted-window median changes from 544.40 to 511.04 ms. Returned rows rise from 81404 to 177157; renderer sampled CPU rises from 38.78 to 74.52 seconds and host CPU from 141.48 to 182.89. V8 used peak rises from 374.78 to 659.62 MiB. Listener creation falls from 111679 to 104289 and element creation falls, but more reads and processing still increase allocation/footprint. Recorded activity duration is 157.610 → 199.809 seconds, closely tracking the measured UI phase.

All four producers completed normally with exit0 and empty Jobs. Exact durable audits passed for all three Inventory modes and Plan's 10,100 filesystem operations plus 10,000 verified targets; original DB bytes were preserved. Source content/metadata and product/runtime checks passed. The candidate Plan audit was first attempted before the producer had finished post-close checks; its failed receipt is retained as `candidate-plan-audit.log`. The successful rerun after producer completion is `candidate-plan-audit-final.log`; no DB audit occurred in the premature attempt.

Exact values, intervals, CPU/heap samples and receipt hashes: `summary.json`, `comparison.json`, `history-durations.json`, `producer-provenance.json`, and each run's original logs/result/audit. No new native runs or product edits were made after this pair. Additional drain collection scope remains for parent/user adjudication.

# `build/cadence-measurement-20261108/drain-amplification-review.md`

# Independent review of Inventory drain traffic

This is a read-only finding from the frozen frontend cadence candidate. The
ordinary Inventory windows fell from 434/371/368 to 190/218/200 across
Baseline/Verify/Rebaseline. The same phases issued 844/713/713 versus
8,244/8,282/8,511 `next_events` calls, and the candidate samples lasted
54.89/61.37/61.33 seconds versus 38.14/40.06/41.00 seconds. Sampled host CPU
also rose. The three paired phases support the observed direction on this
fixture. They share one process per arm and do not establish a stable
throughput penalty or its exact attribution.

The application change removes synchronous Inventory rendering on events and
ordinary snapshots before the next browser drain rearm. The unchanged
`bridge.js` settlement path rearms immediately with one owned task drain. The
unchanged `TaskRegistry._drain_admitted` exits its wait as soon as it sees a
reliable ordinary integrity event. The old UI paint therefore supplied
incidental backpressure. The source explains how the candidate can consume
the same reliable stream in smaller prefixes. The native wrapper counts calls
and durations, with no observed per-response update-count metric.

The consequence is amplification of a supported workload through the existing
pump, with an observed resource and duration tradeoff. The candidate adds no
drain loop, parallel observation, idle polling path or new queue population.
The existing one-owner, 64-update and response-byte bounds remain effective.
The exact database audits establish completed durable outcomes and unaffected
input bytes. They do not measure browser-delivered identity or gaps.

The finite source corpus was the base and candidate `acceptTaskUpdate`,
`bridge.js` drain arm/settlement/recovery, `drain.py` reliable offer and
wait/admission loop, `task_snapshot.py` reduction, the V5 integrity-event
contract, `verifier/engine.py` ordinary and post-copy success/recording
composition, existing `test_drain.py` collection fixtures, the native Inventory
helper, and BRIDGE's delivery contract and PERFORMANCE's prior COPY evidence.
The UI change is complete in this corpus. A transport policy correction changes
the explicitly separate reliable delivery timing boundary and needs user scope.

If authorized, extend the existing native fixed 25 ms result-collection wait.
The smallest measured target is ordinary baseline/verify/rebaseline. Use the
exact session mode and phase, a successful `baselined` or `verified` outcome,
null reason and detail, zero omitted details, recording `ok`, and applied/noop
record disposition. Ordinary Verify can produce `baselined` when it first
attests a subject. The production positive post-copy path has mode Verify,
result verified, paired recorded identity and applied/noop disposition. Its
unpaced drain predates this frontend change and belongs in the new outcome only
if approved. Existing COPY eligibility and all prompt bypasses stay intact.

Keep one fixed outer-capped deadline. Reliable control and phase events,
errors, degradation, Gap, terminal records, replay, a full queue, close and
supersession interrupt or bypass the wait. The codec still admits the same
longest ordered byte-bounded prefix and no filesystem or durable operation is
batched. A browser-side sleep cannot preserve the same prompt wake behavior.
Direct production ownership is `drain.py` and BRIDGE. Extend its existing
manual-clock tests for the named ordinary modes and bypasses. Run packaged
drain and interface checks and the affected installed journeys. Compare the
frozen frontend-only diagnostic with a separately frozen transport candidate
on the same Inventory workload. Verify exact ordered browser delivery, gap
and terminal behavior independently of durable DB and process-cleanup audits.

# `build/cadence-measurement-20261108/final-summary.md`

# Final 500 ms full reads / 250 ms local presentation comparison

The final source preserves integrity collection and changes automatic full-window
reads to 500 ms while retaining 250 ms local presentation. It was frozen after
review: 303 package files; app SHA256
`ed0273ddb1ebe6234b7065d6c58099222decaef67cd7831252877105f3ecbc39`.
Only app.js changes logically from integrated; plan.js also differs in raw newline
bytes. `final-identity-check.json` retains exact raw/normalized populations and
hashes; `manifest.integrated.json` preserves the preceding manifest. All earlier
sources, manifests, receipts, failure evidence and fixture ownership remain intact.

The same unchanged producer/instrumentation measured one run per workload per
variant. These remain diagnostic samples, not throughput or percentile guarantees.
No other task test/native activity overlapped the final native phases.

| Workload | Original seconds → final | Full reads | Drain commands | Renderer peak MiB |
| --- | --- | --- | --- | --- |
| Inventory Baseline | 38.135 → 33.367 | 434 → 72 | 844 → 838 | 1367.41 → 356.96 |
| Inventory Verify | 40.059 → 29.842 | 371 → 62 | 713 → 746 | 1284.56 → 326.98 |
| Inventory Rebaseline | 41.005 → 28.910 | 368 → 57 | 713 → 734 | 1245.91 → 334.21 |
| Plan copy + linked Verify | 157.985 → 135.682 | 320 → 260 | 11634 → 3590 | 840.09 → 643.72 |

Final Inventory created elements are 115236 / 98501 / 92925 versus original
168707 / 174437 / 168380; listeners 55902 / 47943 / 44862 versus 74263 / 77168 /
74143. V8 used peaks are 76.96 / 68.81 / 72.18 MiB versus 315.79 / 286.94 / 288.06.
Renderer sampled CPU is 10.80 / 11.06 / 8.69 seconds versus 37.58 / 37.78 / 39.36;
host CPU is 33.45 / 30.42 / 28.94 versus 40.83 / 42.64 / 43.36.

Final Plan creates 226288 elements versus 361809 and 109871 listeners versus
111679; returned rows fall to 65560 from 81404. V8 used peak falls to 270.57 MiB
from 374.78. Host sampled CPU falls to 104.33 seconds from 141.48. Renderer CPU
is still higher, 43.53 versus 38.78 seconds (12.2%), consistent with remaining
local presentation work; this is not a claim that every rendering cost fell.
The final phase is 14.1% faster and renderer peak 23.4% lower in this pair.

The prior integrated 500/250-full-read variant took 199.484 seconds with 684 Plan
reads and 1304.51 MiB renderer peak. The revised cadence removes that measured
cost. `comparison-final.json` includes all four variants (original, frontend-only,
integrated collection, final) rather than discarding the unfavorable intermediate
measurements.

Final same-window read medians are 504.47 / 504.29 / 504.82 ms for Inventory and
507.23 ms for Plan; shifted medians 512.52 / 512.93 / 513.27 and 514.95 ms. Raw
classification includes explicit/viewport/terminal reads; deterministic tests own
strict automatic-read and local-paint cadence guarantees. Local paints were not
separately instrumented. Cumulative handler times include intentional waits and
are not CPU time. No ETW/GIL/Defender attribution was performed.

Exact durable audits passed for all three final Inventory modes and Plan's 10100
filesystem operations plus 10000 verified targets. Recorded activity durations
are 31.735 / 28.420 / 27.735 seconds and 135.242 seconds respectively, confirming
the improvement is not just terminal presentation. Source content/metadata,
frozen package, helper and runtime identities all pass. Native final Inventory
and Plan close at process times 110.146 and 152.349 seconds, respectively, with
exit0 and empty Jobs; both producers subsequently completed0. No owned process
remains, and all fixture/profile mappings remain in fixtures.jsonl and manifests.

Separate real-browser reliable identity/no-Gap/terminal/release evidence remains
`../integrity-drain-20261108/evidence/runs/native-02/result.json`; drain and bridge
bytes are unchanged by this final app-only revision. Database audits are not used
as a substitute for that delivery evidence.

Final artifacts: `comparison-final.json`, `summary.json`, `history-durations.json`,
`producer-provenance.json`, `final-identity-check.json`; original logs/results and
audit copies under `runs/runs/final-inventory-01` and `runs/runs/final-plan-01`.

# `build/cadence-measurement-20261108/integrated-summary.md`

# Integrated cadence + integrity collection diagnostics

One run per workload per frozen variant, same unchanged performance producer and
instrumentation; these are diagnostics, not percentile or throughput guarantees.
`baseline` is exact Git archive 39255ca3; `candidate` retains frontend cadence and
allocation changes only; `integrated` adds successful ordinary/linked integrity
collection. The integrated package has 303 files, exactly one normalized change
from candidate (`drain.py`, SHA256
`0ec4454491dfedfe87867b01ecdd612897f98553f27c0920918cf40eb84beaf0`).
Original manifest is preserved as `manifest.frontend-only.json`; population,
helper identity and complete freeze provenance are in `integrated-identity-check.json`.

Values below are original → frontend-only → integrated.

| Phase | Seconds | Full window reads | Drain commands | Renderer private peak MiB |
| --- | --- | --- | --- | --- |
| Inventory Baseline | 38.135 → 54.887 → 44.859 | 434 → 190 → 143 | 844 → 8244 → 1021 | 1367.41 → 761.45 → 567.26 |
| Inventory Verify | 40.059 → 61.366 → 41.285 | 371 → 218 → 126 | 713 → 8282 → 951 | 1284.56 → 984.89 → 538.20 |
| Inventory Rebaseline | 41.005 → 61.335 → 40.792 | 368 → 200 → 125 | 713 → 8511 → 952 | 1245.91 → 855.82 → 468.82 |
| Plan copy + linked Verify | 157.985 → 199.955 → 199.484 | 320 → 697 → 684 | 11634 → 11882 → 4729 | 840.09 → 1462.60 → 1304.51 |

Inventory integrated created elements are 118957 / 108290 / 107399 and listeners
56336 / 51282 / 51316; V8 used peaks are 143.23 / 120.80 / 129.05 MiB. Its renderer
CPU is 18.80 / 13.75 / 14.52 seconds, compared with original 37.58 / 37.78 / 39.36
and frontend-only 27.81 / 28.86 / 26.72. Integrated host CPU 45.94 / 42.66 / 42.78
is near original 40.83 / 42.64 / 43.36, versus frontend-only 76.53 / 84.86 / 86.98.
The collection removes drain amplification; Verify/Rebaseline duration returns
near original, while this single Baseline sample remains 17.6% slower.

Plan integrated creates 231255 elements and 108642 listeners, versus original
361809 / 111679. However it returns 174386 rows versus original 81404, and V8 used
peak is 602.14 versus 374.78 MiB. Renderer CPU is 65.44 seconds versus original
38.78 and frontend-only 74.52; host CPU is 159.81 versus 141.48 and 182.89. Thus
collection helps relative to the frontend-only variant, but the faster full
loaded-window refresh still costs approximately twice the reads, with 26% longer
execution and 55% higher renderer peak than original in these samples. Fewer DOM
allocations do not establish lower total JS allocation or footprint.

Integrated same-window medians are 255.12 / 253.93 / 254.69 ms for Inventory and
255.79 ms for Plan; shifted-window medians are 519.61 / 514.83 / 514.90 and 514.61
ms. Classification includes explicit, viewport and terminal reads, so it is not
a strict automatic-cadence assertion. Deterministic tests own those guarantees.
The cumulative handler wall times include intentional collection waits and must
not be interpreted as CPU cost. No ETW/GIL/Defender attribution was performed.

Recorded integrated activity durations are 43.060 / 39.755 / 39.272 seconds for
Inventory and 199.235 for Plan: the observed execution cost is not merely UI
terminal delay. Exact durable audits passed for all modes, all 10100 Plan
filesystem operations and 10000 verified targets. All producers completed0;
all native apps closed normally with empty Jobs; source metadata/content and
frozen product/helper/runtime identity checks passed. No additional native runs
were started after this integrated pair.

The separate finite real-browser delivery diagnostic passed for ordinary and
linked integrity: see `../integrity-drain-20261108/summary.md`. Its producer/browser
identity comparison, no-Gap and terminal/release evidence are distinct from these
database audits. Its title-mismatch first attempt and corrected retry are both
preserved; neither changed this performance producer.

Machine-readable values: `comparison-integrated.json`, `summary.json`,
`history-durations.json`, `producer-provenance.json`; original receipts and audit
copies remain under `runs/runs/`. Earlier frontend-only comparison and failed
premature Plan audit remain intact for chronology. Analysis-only scripts do not
alter measurement producer dependency identity.
