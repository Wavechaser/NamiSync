# Performance measurement methods and observations

This is the single owner for measurement fixtures, profiles, scaling axes,
sample aggregation, commands, artifact provenance and results. It records
historical observations at their measured revisions; it does not turn them
into a guarantee for the current checkout. [DEFENSE](DEFENSE.md#7-quantitative-evidence-and-measurement-authority)
owns evidence authority and consequence. [PRESENTATION](PRESENTATION.md#focused-scale-acceptance),
[BRIDGE](BRIDGE.md#evidence-and-ongoing-checks) and [INTERFACES](INTERFACES.md#sh-g-release-criteria)
retain behavior and gate decisions. AB-2 moved Plan/UI latency and empirical
representation-memory collection to optional developer observations while
preserving fixture/action, counted-work and independent release/custody gates.

## Reference profile and collection

The retained BR-G-42 profile is Windows 11 Pro build 26200, i7-13700K
(16 cores/24 logical processors), 63.7 GiB RAM, WD_BLACK SN850X 4 TB NVMe
for repository, fixtures and SQLite, CPython 3.13.14, SQLite 3.50.4, AC
power and no unrelated sustained workload. Warm p95 uses at least 30
samples; cold maxima use at least five fresh-process or cold-projection
samples. Record raw samples, source/runtime/profile, fixture seed, statistic,
child count, p95 and maximum. These identify reference evidence, not exact-
version launch admission. DEFENSE §7 governs changed-profile decisions.
The five-child counts describe historical acceptance collections and any
separately retained gate; a selected optional Plan/UI case below is a single
diagnostic child, not a replacement aggregate.

The Plan corpus has 100,000 operations plus up to 20,000 structural/group/
ghost rows; the information-heavy variant adds 120,000 notices for 240,000
projection rows. It has depth 32, prior-path ancestors, seed 0x4E414D49,
stable typed-code cycling, indexed ASCII paths, null initial detail and
duplicate occurrences. Sort cases cover balanced/widest siblings, tied or
unavailable keys, Unicode names, both directions and reset. Changed-sort
and unchanged windows remain separate; memory samples include retained
state and construction overlap. A seventh view after six populated views
exercises bounded retention without prescribing a cache mechanism. Key,
projection, comparator, index, publication or retention changes reopen
affected evidence. The source-owned runtime admission bounds are independent.

## Source-linked historical observations

All values below are independently derived from committed compact JSON.
The M1-7 Plan profile was accepted at `3c3bbbc` in the 2026-09-16 P9
collection; the M1-8 U-v2 profile at RC-1 `3ea4e6b` on 2026-09-24.
The compact contracts and authority artifacts bind their specific source,
fixtures and profile; the recorded bindings have not been revalidated
against today's checkout. P2 receipt values belong to its earlier `4bbf943`
build and are superseded by U-v2 for the corresponding delivered UI bytes.

| Source/revision and fixture | Recorded profile and limitation | Statistic/unit | Children; samples | Observation | Limit |
| --- | --- | --- | ---: | ---: | ---: |
| [M1-7 compact measurements](../tests/interfaces/web/m1_7_plan_compact_measurements.json), `3c3bbbc`; cold base, 100,000 operations/120,000 rows | P9 reference; measured revision only | maximum ms | 5; 5 | 1,752.5309 | 2,000 |
| [M1-7 compact measurements](../tests/interfaces/web/m1_7_plan_compact_measurements.json), `3c3bbbc`; cold information-heavy, 100,000 operations/240,000 rows | P9 reference; measured revision only | maximum ms | 5; 5 | 2,764.6222 | 4,000 |
| [M1-7 compact measurements](../tests/interfaces/web/m1_7_plan_compact_measurements.json), `3c3bbbc`; unchanged 256-row window | P9 reference; measured revision only | nearest-rank p95 / maximum ms | 5; 30 | 1.6548 / 1.6856 | 250 / 500 |
| [M1-7 compact measurements](../tests/interfaces/web/m1_7_plan_compact_measurements.json), `3c3bbbc`; incremental retained construction overlap | P9 reference; projection memory only | maximum bytes | 5; 5 | 280,768,512 | 335,544,320 (320 MiB) |
| [M1-8 U-v2 result](../tests/interfaces/web/m1_8_execution_ui_result.json), `3ea4e6b`; worst cold click (destructive start) | U-v2 installed headed; measured revision only | maximum ms | 5; 5 in case (40 across eight cases) | 20.3 | 50 |
| [M1-8 U-v2 result](../tests/interfaces/web/m1_8_execution_ui_result.json), `3ea4e6b`; worst warm receipt p95 (cancel) | U-v2 installed headed; measured revision only | nearest-rank p95 ms | 5; 30 in case (150 across five cases) | 72.0 | 100 |
| [M1-8 U-v2 result](../tests/interfaces/web/m1_8_execution_ui_result.json), `3ea4e6b`; worst warm receipt maximum (cancel) | U-v2 installed headed; measured revision only | maximum ms | 5; 30 in case | 73.3 | 250 |

M1-7's [compact contract](../tests/interfaces/web/m1_7_plan_compact_contract.json)
and companion authority, plus U-v2's [authority](../tests/interfaces/web/m1_8_execution_ui_authority.json)
and [receipts](../tests/interfaces/web/m1_8_execution_ui_receipts.json),
carry the source and profile bindings and raw sample membership. The P2
[authority](../tests/interfaces/web/m1_8_execution_receipt_authority.json),
[receipts](../tests/interfaces/web/m1_8_execution_receipt_receipts.json) and
[result](../tests/interfaces/web/m1_8_execution_receipt_result.json) record
the earlier 6.8/7.3 ms window and 58.8/65.1 ms start p95/max observations.
Do not combine maxima and p95 across endpoints into one score.

## Selected Plan and execution UI observations

Run an optional case through `python -m tools performance --list`, then
`python -m tools performance FAMILY CASE --json build/REPORT.json`. Installed
Execution-receipt and execution-ui cases also require `--installed-root`
pointing to the wheel's `site-packages`; a relative path resolves from the
invoking directory. The driver executes the real component or installed headed
endpoint in a bounded child and writes one report plus a sibling raw child log.
The report names the case, fixture/action correctness, raw samples, current
revision/dirty state and runtime. Failure or timeout is an incomplete report
with a nonzero command exit; an elapsed time cannot turn a wrong or unfinished
action into a successful observation. Each invocation is a diagnostic sample,
not an acceptance run or a new speed/memory guarantee. The historical targets
above remain comparison context only.

The Plan fixture uses seed `0x4E414D49`, 100,000 operations, 120,000 base
projection rows and a 240,000-row information-heavy variant with 120,000
warnings. It exercises depth 32, prior-path rows, widest siblings, raw-key
order, selection and actual changed/unchanged views. The public Plan cases
are component measurements selected by their compact-contract metric IDs;
the receipt/UI adapters own the current installed headed cases.
Cold cases retain one sample; warm cases retain six. The optional projection
memory case measures retained construction overlap but does not certify a
fixed object graph or SH-G-15. Functional tests independently check fixture
counts, sibling/order witnesses, exact selection membership, scoped actions,
typed replies, settlement and false fast responses. Counted-work tests remain
in the owning presentation/interface tests.

Four Plan component observations use the delivered rootless public view while
the frozen historical contract records the earlier rootful view: unchanged
window total 239,999 rather than 240,000, hostile search two rather than three
visible rows, and memory-overlap base/staged window totals 119,999/239,999.
The changed-collapse case now collapses the visible Previous paths folder and
reads its 256-row window, instead of collapsing the hidden synthetic Plan root.
Those endpoints are not direct apples-to-apples latency comparisons with the
old rootful observations. The underlying 120,000/240,000 projection populations
and the other contract correctness witnesses remain checked; no historical JSON
or contract byte was rewritten.

The M1-8 receipt adapter settles the installed rootless public view with
119,999 visible rows from 120,000 projection nodes. Its first group is the
independently derived `NamiSyncPriorV1` Previous paths row. Each selected
receipt case uses six samples after an equivalent untimed warmup. The execution
UI adapter keeps eight cold click-feedback and five warm receipt endpoints;
cold cases have one sample and warm cases six. Its guarded JavaScript probe is
`tools/performance/execution_ui_probe.mjs`. It observes actual command/reply
identity and first-frame feedback, verifies eventual settlement, and rejects
refusal, unrelated state and missing dispatch. These observations use the
installed host and do not exercise filesystem execution as a timing endpoint.
For the seven adapted command-feedback cases, the current receipt accepts
either a pending frame or an already accepted successor frame, with all other
action/fixture fields still exact. The child and parent validate that current
receipt; the frozen historical busy/pending-frame JSON remains unchanged.

For a fresh installed observation, build and install a wheel into a separate
tool-owned directory and pass that installation as `--installed-root`. The
selected runner checks that NamiSync imports from the installed tree; the
project Python supplies development dependencies. Record the wheel and
installation used alongside the JSON, and preserve the raw log when diagnosing
failure. The 300-second child deadline is containment, not a latency target.

The committed [M1-7 compact contract](../tests/interfaces/web/m1_7_plan_compact_contract.json),
[authority](../tests/interfaces/web/m1_7_plan_compact_authority.json) and
[measurements](../tests/interfaces/web/m1_7_plan_compact_measurements.json),
and the M1-8 [P2](../tests/interfaces/web/m1_8_execution_receipt_result.json)
and [U-v2](../tests/interfaces/web/m1_8_execution_ui_result.json) records
remain byte-identical historical evidence at their stated revisions. Their
readiness children, 35-case/78-attempt collection indexes, source-hash
certificates and legacy validators were retired from current execution by
AB-2. They neither authenticate a new checkout nor prescribe a new selected
case. The old full methods and exact validators remain recoverable from the
recorded Git revisions; use the current selected-case procedure above for
new exploratory observations.

## Executor and verifier methods

### Executor measurements

```powershell
.\.venv\Scripts\python.exe -m tools executor E:\Corpus E:\RigWork --repeat 5
.\.venv\Scripts\python.exe -m tools executor E:\Corpus E:\RigWork --prepare-each --repeat 5
.\.venv\Scripts\python.exe -m tools executor E:\Corpus E:\RigWork --template E:\PreState --verify-readback
```

Without `--template`, the default repeated benchmark prepares one static plan
in memory. The target must be empty and the selected plan may contain only
MKDIR and absent-target COPY operations. The harness first performs an exact
owned-target reset, then scans, plans, and selects once. Every sample receives a
fresh `ExecutionSet`, run ID, event tape, recorder, backend, and filesystem
adapter. Unless `--no-preflight` is explicit, the first fresh set is preflighted
immediately before execution; later samples reset the target and execute a new
set without replanning or re-preflighting. Execution time still covers the
complete public executor call, including copy publication, metadata, recording,
and final directory finishing. Output-manifest validation/publication and reset
receipts happen outside `execute_seconds`.

Every repeated sample must publish the same operation-keyed digest and size
evidence. After the last sample the harness rescans the source and requires the
complete source snapshot to match preparation; any membership, identity, stat,
or digest drift invalidates the batch. The plan is never serialized. Use
`--prepare-each` to rescan, replan, and preflight every empty-target sample.
Template workloads always prepare each sample because rematerialization changes
target identities; update, delete, NOOP, and other target-dependent plans are
therefore never fed through the static-plan path. Template setup time is
reported separately from scan, plan, preflight, and execution time. Supplying
`--prepare-each` with `--template` is refused because it would be a misleading
no-op.

The executor's published digest comparison detects same-stat content changes
between samples. Content changed after preparation but before the first sample,
with all scanned stat fields deliberately restored and then held stable, is not
distinguishable without another full plan-time content read; use a quiescent
source corpus.

Pipeline diagnostics are enabled by default in the tools while remaining off by
default in production. The harness samples each copy because
`NativeCopyBackend.last_metrics` retains only the most recent one. Reports
include reader blocking, writer starvation, payload high-water, reserved bytes,
chosen chunk sizes, and copy-backend wall time. `--no-metrics` disables both the
executor diagnostics and the per-copy timing wrapper. With diagnostics enabled,
each accepted sample prints copy count and bytes, summed backend wall time,
executor time outside the copy backends, summed reader-blocked and
writer-starved time, maximum payload high-water, reserved bytes, and the
distinct chunk sizes used. Detailed metrics therefore remain useful without a
JSON report.

Every selected operation must settle with a complete successful terminal
result whose typed items agree with the reviewed operation paths and outcomes,
non-degraded recording/audit, and complete invariant-valid published evidence.
A NOOP's normal `SKIPPED` outcome is accepted. Plans with safety exclusions and
any other failed, deferred, incomplete, degraded, or drifted sample invalidate
the whole batch.

All accepted raw samples are retained in order without report-time rounding.
For repeated runs the console prints N, minimum, median, and maximum execution
time plus the median of the per-sample throughput values. No percentile,
outlier deletion, or implicit warm-up discard is applied.

`--verify-readback` prints its own result even without `--json`. Zero candidates
is valid for an all-NOOP/non-copy plan; otherwise every published candidate and
byte must verify with non-degraded recording.

### Shared root admission optimization — 2026-09-28

The core candidate reuses native bindings and replaces default admission's
second anchor discovery with a volume-information query at the admitted anchor.
Consumer invocation holds are not integrated in this measurement.

`build/root-admission-optimization-20260928/core/measure_admission.py` measures
1,000 sequential default admissions of `F:\GitHubRepositories\NamiSync` on
NTFS in a fresh process per revision, with Python 3.13.14. Baseline `b8baf42d`
runs from its isolated checkout; the candidate is the core edit over `3c8b4b41`,
identified by source SHA-256 in `resume/admission-finalpath-serialized.json`. Both receipts record
the imported source, runtime, root and native call counts.

| Observation | Baseline | Core candidate |
| --- | ---: | ---: |
| `GetVolumePathNameW` calls | 2,000 | 1,000 |
| `GetVolumeInformationW` calls | 1,000 | 1,000 |
| Median admission, microseconds | 985.7 | 488.95 |
| p95 admission, microseconds | 1,248.2 | 687.1 |

These sequential single-root diagnostics establish the call reduction and
describe the observed timing; they do not establish depth scaling,
instrumentation neutrality or executor throughput. Consumer measurements follow
below; the core figures remain a separate endpoint.
[M1_PLAN](M1_PLAN.md#root-admission-optimization--2026-09-28) owns that goal and
the equivalence gate.
The retained `admission-finalpath.json` diagnostic overlapped the ordinary test
run; the table uses the subsequent sample with those gates finished.
Earlier identity-only candidates and their rejected native witnesses remain
retained separately. The final-path correction has passing one-/two-swap
regressions and confirmed hold lifetime/release witnesses on NTFS and exFAT
(K:, serial `BA1F1F45`). `resume/exfat-invocation.txt`, `exfat-volume.json` and
`exfat-finalpath.xml` bind the external fixture to the frozen implementation.
The non-admin subst fixture failed full volume admission (native error 144),
so it does not establish a held-mode transition. Exact mapping removal was
verified; strict alias rejection has a focused comparison witness.

### Executor invocation holds — 2026-09-28

The initial hold-only observation below predates the required per-access
held-handle attribute guard. It remains historical timing evidence, not acceptance
of an unchecked hold. The corrected observation is recorded after its table.

The frozen executor candidate over `6536c04` was measured after the ordinary
gate finished, using the same preserved 1,000 × 4 KiB F: source and a fresh G:
rig workspace. Three serialized samples without the native-call wrapper took 11.059, 11.204
and 11.708 seconds (median 0.349 MiB/s), versus the earlier assessment's
28.2 seconds / 0.14 MiB/s. Each sample copied and verified all 1,000 files;
the source recheck was unchanged and manifest-scoped teardown succeeded.
Both roots report held mode. Backend copy time was 0.491–0.522 seconds;
10.568–11.186 seconds remained outside the backend. This does not isolate
all remaining path costs, and the above-1-MiB/s goal remains unmet.

A separate native-call wrapper counted only `execute`, on isolated baseline
`b8baf42d` and the frozen candidate, using identical driver bytes and fresh
targets. Its timing is instrumented diagnostic data, excluded from the samples.

| Project ctypes Win32 binding calls during execute, 1,000 copies | Baseline | Held candidate |
| --- | ---: | ---: |
| `GetVolumePathNameW` | 48,000 | 6,002 |
| `GetVolumeInformationW` | 20,000 | 6,002 |
| `CreateFileW` / `CloseHandle` each | 2,000 | 2,002 |
| `GetFinalPathNameByHandleW` | 0 | 2 |
| `GetFileInformationByHandleEx` | 4,000 | 4,000 |

Receipts and source/driver hashes live in
`build/root-admission-optimization-20260928/resume/`: `executor-held.json`,
`executor-baseline-counts.json`, `executor-held-counts.json` and corresponding
logs/run reports. The independent K: exFAT root-scope witness passes, while
the copy witness fails with error 87. Read-only metadata queries expose a
pre-existing unsupported handle-identity query; the first failing copy API is
not traced. [BUGS](BUGS.md) records that separate limitation. No exFAT copy
throughput or compatibility success is inferred from the root-hold evidence.

The corrected core/executor guard uses `FileBasicInfo` on the held handle before
admission reuse, retaining one final-path confirmation. Following its completed
ordinary/import/oracle/differential gates, three serialized samples on the same
preserved F: source and a fresh G: target took 15.271, 15.711 and 15.047 seconds
(median 0.256 MiB/s). All 1,000 copies and readbacks per sample passed; the source
scan was unchanged and manifest-scoped teardown completed. Backend copy time
was 0.564–0.594 seconds, with 14.481–15.117 seconds outside the backend. The
goal remains unmet. These samples are slower than the earlier unchecked hold
samples; no controlled per-query timing attribution is claimed.
Receipts: `resume/executor-attributes.json` and its log under the same evidence
root. Standard rig metrics are enabled; the separate binding-call wrapper is
excluded from these timing samples. NTFS conversion/regression witnesses and
two K: production guard/lifetime tests establish correctness separately.
The same execute-only counter driver records 6,002 anchor and 6,002 volume-
information calls, 2,002 opens/closes, two final-path confirmations and 31,998
handle-information calls (4,000 in the unchecked hold sample). The added current-
attribute checks preserve the reduced pathname/volume work. The counted run
also copied and verified all files and cleaned its owned target; its elapsed
time is instrumented diagnostic data. `executor-attributes-counts.json` and
`executor-attributes-counted-run.json` retain hashes, imports and raw counts.

### Executor assessment — 2026-09-27

Read-only assessment of `milestone1-adelbert` at
`0e4595e4142fc78cfbf8e274832520a4344f3b5e`. These are Tier 0 diagnostic
observations and optimization leads, not release criteria or approved changes.
No production, test, rig, policy, or settlement-baseline files were changed.
Executor history includes September 8 runtime consolidation and September 20
capacity-failure handling; early August is not its last meaningful change.

**Profile and evidence.** Windows 11 Pro 26200, i7-13700K, 63.7 GiB RAM,
CPython 3.13.14, xxhash 3.8.1; F: and G: are separate 4 TB WD_BLACK SN850X
NVMe devices (disk 3 and disk 5), both NTFS. The existing read-only
`F:\NamiSyncExecutorBenchSource` supplied the five size bands below. Its original
generator seed was not reconstructed; membership/stat identity is retained in
`source-manifest.json`, and the rig checks published digest consistency and
source snapshot stability. No cache eviction, device-counter saturation study,
or control of unrelated desktop activity was performed. Storage benchmarks
were serialized; read-only source reviews ran alongside them. Results describe
buffered repeated-source workloads, not cold reads or device peak bandwidth.

Local raw evidence and temporary drivers are retained in
`build/executor-assessment-20260927/`: `baseline.ps1`, `followup.ps1`,
`finalcases.ps1`, `diagnostic.py`, `fg-*.json/log`, `gf-1x4GiB.json/log`,
`stages-*.json/log`, `poll-*.json/log`, `no-metrics-small.json/log`,
`profile-*.prof/txt/json/log`, environment receipts, source hashes, and derived
`summary.json`. `summarize.py` derives medians/ranges from raw samples without
discarding any run. Each invocation used a fresh dedicated target named
`NamiSyncExecutorAssessment-20260927-*`; all such F:/G: roots and rig artifacts
were subsequently removed through manifest-validated rig cleanup. The original
F: corpus remains in place. Ignored build evidence is local, not committed
acceptance authority. Relevant source, driver, runtime, fixture, or storage
changes require new observations before carrying these findings forward.

**Baseline.** Each F: band ran five times in one fresh process, using one
empty-target prepared plan, initial preflight, metrics enabled and readback on
every sample. All 25 executions and readbacks succeeded with recording OK and
zero remaining payload reservations. Times cover the public executor call;
preparation, preflight, manifest handling, cleanup and readback are separate.
The recorder/event sink are the rig's in-memory seams, so this does not measure
SQLite, history, workflow event validation or GUI delivery costs.

| F: → G: workload | Execute median [min–max], s | Median MiB/s | Backend median, s | Outside backend median, s | Reader blocked median, s | Writer queue wait median, s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,000 × 4 KiB | 28.248 [27.367–29.745] | 0.138 | 0.512 | 27.739 | 0 | 0.114 |
| 512 × 128 KiB | 14.068 [13.983–16.096] | 4.55 | 0.291 | 13.775 | 0 | 0.074 |
| 64 × 4 MiB | 2.051 [2.019–2.107] | 124.8 | 0.204 | 1.841 | 0 | 0.103 |
| 4 × 128 MiB | 0.424 [0.414–0.449] | 1,207.4 | 0.191 | 0.236 | 0 | 0.048 |
| 1 × 4 GiB | 2.287 [2.104–2.385] | 1,791.3 | 1.592 | 0.733 | 0.062 | 0.135 |

Columns are independently aggregated; their medians need not sum. A reverse
G: → F: 4 GiB control, using a rig-created and verified G: source, returned
1.987 s median [1.818–2.029], 2,061.6 MiB/s across three samples in one process;
all readbacks passed. Direction, source-root spelling and run order differ, so
this is not a controlled device asymmetry claim.

The [historical hash-refactor table](obsolete/M1_HASH_REFACTOR.md#28-final-m1-executor-results)
records 2.426 s for 1,000 × 4 KiB and 2.014 s for 4 GiB on F: → G:.
Today's small-file result is substantially slower, while the large-file result
is much closer. That old single-pass driver/profile was not rerun: the ratio
is historical context, not a causal regression measurement or attribution to
one commit. Its `Final` column is not equated with today's outside-backend time.

**Where the small-file time goes.** A separate instrumented 1,000 × 4 KiB
run took 27.901 s, including 0.524 s in the backend. Wrappers around synchronous
runtime/native functions retain call counts and nested inclusive/exclusive
elapsed time. Inclusive rows overlap and must not be summed with their parents.
They do not partition the concurrent reader/hasher/writer internals. One sample
does not prove instrumentation neutrality.

| Observed function or stage | Calls | Inclusive seconds |
| --- | ---: | ---: |
| Native root revalidation | 27,000 | 16.832 |
| Native root-relative resolution, overlapping root revalidation | 13,000 | 10.005 |
| Temp metadata finalization, including its file flush | 1,000 | 0.453 |
| Atomic new-file publication | 1,000 | 0.188 |
| Published metadata observation/conditional repair | 1,000 | 0.303 |
| Parent directory flush | 1,000 | 0.311 |
| Recorder call wrapper, in-memory recorder | 1,000 | 0.017 |
| Reliable settlement | 1,000 | 0.037 |

Root revalidation consumes about 60% of this instrumented execution, including
its nested work. There are 14 full root admissions and 13 chain-only admissions
per COPY; `resolve()` repeats chain admission even immediately after
`_resolve_target_path()` has performed full admission. Freshness across streaming,
callbacks, finalization and publication remains necessary; repeated adjacent
derivation is a separate optimization question.

The supplementary small-file cProfile receipt records 508,000
`to_extended_length_path` calls, 311,000 `lexical_absolute_path` calls and
1,401,000 `_validate_absolute_path_spelling` calls. The one-file profile repeats
exactly 1,401 spelling validations and stage instrumentation repeats 27 root
revalidations. These are observed counts on these fixtures. The small profile
slowed execution to 64.064 s; worker-thread cumulative timings also overlap.
Do not use cProfile timing sums or percentages to predict an unprofiled gain.
Source inspection identifies `lexical_absolute_path`'s ordinary → extended →
ordinary roundtrip and repeated component validation as avoidable-work leads.

All 1,000 directory flushes succeeded. Exactly 1,000 metadata handles/file
flushes were used, consistent with one temp finalization and no post-publication
repair reopen on this corpus. The existing conditional repair is doing its job.
A diagnostics-off control still took 27.190 s median [27.163–27.978] over three
samples; diagnostics cannot explain the dominant fixed cost. This control was
later, not interleaved, so it does not establish a precise instrumentation tax.

**Pipeline bubbles and finishing.** The 4 GiB baseline reaches the 32 MiB
reservation cap but has only 0.062 s median reader blocking and 0.135 s median
writer queue waiting inside a 1.592 s median backend call. This does not show
a large polling-induced bubble. A separate interleaved nine-process probe used
the existing `poll_seconds` constructor seam, leaving production defaults intact:

| Poll interval | Fresh processes | Execute median [min–max], s | Backend median, s |
| --- | ---: | ---: | ---: |
| 10 ms, default | 3 | 1.994 [1.837–2.046] | 1.322 |
| 1 ms | 3 | 2.047 [1.828–2.099] | 1.311 |
| 0.1 ms | 3 | 1.936 [1.926–1.946] | 1.334 |

Order was default/1/0.1, default/0.1/1, default/1/0.1 ms. Every readback passed.
Backend medians stay within 1% of the default; the end-to-end spread does not establish a
material polling improvement. These nine observations are separate from the
baseline, not pooled with it. The rig report does not encode the override;
the retained driver and filename identify it.

Writer wait includes startup, queue acquisition and EOF handoff; reader blocking
excludes actual read latency and ordinary coordinator work. Reservation high-water
includes the next whole-chunk reservation before read, even the EOF probe; it is
not actual memory use or queue occupancy. Low small-file high-water therefore
does not prove underutilization, and these waits are not device utilization.
In particular, the 4 MiB band's approximately 0.103 s writer queue wait is only
one part of its 0.204 s backend and 2.051 s whole execution. Its fixed per-file
work is the larger opportunity.

A separate 4 GiB stage run took 2.158 s: backend 1.385 s and the required temp
file flush 0.685 s. There is a real serial durability tail, but removing that
flush would weaken the contract. A whole-corpus stage run (1,582 files, including
the 51-byte corpus marker, plus five directories; 4,931.9 MiB) took 44.388 s,
of which 2.561 s was backend work. Final directory completion took 0.016 s;
all 1,587 directory flush attempts succeeded. A template case with 60 COPY and
four UPDATE operations took 2.269 s; four hardlinks took 0.0006 s and four atomic
replacements 0.0008 s, with 68 successful parent flushes taking 0.024 s. All
published bytes verified. This covers ordinary hardlink-backed updates, not
MOVE_UPDATE, ACL preservation, readonly/tunneling repair, cancellation or a
hardlink-unsupported backup performance profile.

**Review correction and native-call attribution.** User review correctly
distinguished fresh evidence from preservation of today's probe APIs/counts.
The initial recommendation to keep every native probe and optimize only pure
derivation first was too restrictive. cProfile charges ctypes execution to its
Python caller: `_observe_root_anchor` self time is not pure Python path work,
although it also includes buffer allocation and other unprofiled native work.

A supplemental read-only diagnostic, `root_probe_review.py/json`, timed the
actual bound APIs on the existing F: 4 KiB corpus directory. At review the branch
had advanced to `6de6d1c0`; executor and core source are byte-unchanged from the
original measured revision. Original rig receipts remain tied to that original
revision, not reissued for the newer checkout. In one process,
1,000 full admissions took 1.131 s total: 2,000 `GetVolumePathNameW` calls took
0.577 s, and 1,000 `GetVolumeInformationW` calls took 0.032 s. Median individual
calls were 269.6 and 28.3 microseconds respectively; full admission median was
1,083 microseconds. Separately, 1,000 open-directory/read-`FILE_ID_INFO`/check-basic-
attributes/close probes had a 30.4 microsecond median [26.9–289.4]. This is a
single-root microdiagnostic, not an executor speedup or depth-scaling result.
Native mount discovery is therefore a priority alongside repeated derivation.

The same probe confirmed `st_dev == 0x98AC4C7AAC4C5542`, equal to the handle's
64-bit serial, with low 32 bits matching `GetVolumeInformationW`'s `AC4C5542`.
[CPython 3.13.14's stat implementation](https://github.com/python/cpython/blob/v3.13.14/Python/fileutils.c)
obtains volume identity from file-stat/handle information. The current NamiSync
handle-identity adapter explicitly truncates the serial to 32 bits; a proposed
full-width root binding must retain the original 64-bit value separately.

**Revised investigation order, without production implementation authorization:**

1. Reduce calls and reconstruct immutable facts less often. Build the two
   reviewed `RootAuthority` values once per execution invocation and pass them
   through without rebuilding them in the native adapter. This retains facts,
   not successful admission. Add direct lexical normalization while preserving
   UTF-16, namespace and before-normalization rejection rules. A single no-follow
   stat can supply entry type, attributes, identity and volume evidence;
   `_stat_path` need not perform lexists/lstat/stat plus another path-volume
   lookup. Compare its observed volume against admitted expectations, preserving
   the existing serial representation and filesystem capability policy. Likewise,
   classify a root component from its lstat instead of a later following is_dir.
   Preserve missing-path/error behavior deliberately: the legacy executor adapter
   and tests currently encode the second is_dir result as authoritative.
2. Discover the anchor once per admission where that API is still needed, and
   query volume information using the admitted anchor. Current `admit_root`
   independently re-observes and compares the anchor after chain traversal;
   replacing the second observation with the first value would make that equality
   check tautological. Explicitly revise this observation policy and its tests
   rather than claiming that two independent observations still occur. For an
   ordinary drive-root anchor, a fresh no-reparse chain plus observed volume
   identity is the candidate evidence; mounted-folder anchors need their own
   binding. A reparse tag alone identifies a kind, not a particular mount target.
3. Define one admission per actual access/effect step and reuse it only within
   that step. Source open, temp creation, finalization, final guards, publication
   and published-file observation are useful COPY phases, not a universal six-
   check maximum: owned-temp cleanup, backup/security work, retries and resumes
   also have access/effect boundaries. Prefer a combined native operation over
   a general `already_admitted=True` bypass. Keep child containment and required
   leaf guards; do not retain successful admission across intervening work.
4. Evaluate fresh root-handle identity against a baseline established by full
   admission. The [Windows identity tuple](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_info)
   supplies a 64-bit volume serial and 128-bit file ID, stronger object binding
   than anchor spelling plus the existing 32-bit volume serial. It does not make
   subsequent pathname operations handle-relative or atomic. Opening with
   [OPEN_REPARSE_POINT](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)
   does not certify all intermediate components or descendants; specify whether
   root-object continuity replaces repeated ancestry validation, while retaining
   required child-path checks. Decide baseline lifetime across pause/resume,
   handle retention/identity reuse, mounted-folder handling, unsupported identity
   behavior and binding to reviewed evidence. Fewer user-space component probes
   is a credible gain; constant syscall count does not imply depth-independent
   kernel lookup latency. A shallow/deep fixture comparison remains outstanding.
5. Keep current single-handle finalization and conditional metadata repair.
   Small-file worker elimination could save at most the measured backend portion
   (about 2% on this fixture), while recorder/settlement CPU is smaller still.
   Directory-flush batching, overlapping publish with the next file, or retaining
   multiple prepared files changes durability, cancellation and effect ownership;
   the measurements do not justify starting there. The large-file flush tail
   merits investigation only under a design preserving durable publication.
6. Runtime condensation beyond admission work has limited remaining value:
   `_ProgressTracker.__init__`
   can combine its two plan walks and avoid its temporary settled-ID set while
   preserving signed-64 sums and resumed progress. Existing shared rename and
   publication-observation mechanics already address larger duplication. Earlier
   [reduction dispositions](obsolete/REDUCTION_FOLLOWUP.md#scope-and-decisions)
   shelved pause/cancel merging, recording-tail builders and verdict compression;
   their different effect/recovery order remains a reason to keep them distinct.
   Structural settlement work still requires EXECUTOR's protected oracle gate.

Across this assessment, 23 benchmark invocations produced 47 successful execution
samples, including 42 successful readback samples (the diagnostics-off control
and cProfile runs omitted readback). Existing rig/pipeline tests passed 80/80.
Independent source/instrument review checked timing boundaries, call attribution,
poll overrides and metric limitations. These checks support the assessment;
they do not certify a future optimization or replace its required gates.

### Benchmark reports

Console output is the artifact-free default. `--json PATH` opt-in publishes one
versioned JSON document for the complete valid invocation, not one JSONL row per
sample. The envelope separately owns configuration, one-time batch preparation,
post-batch validation, ordered raw samples, and the N/minimum/median/maximum
summary; static-plan samples do not duplicate scan, plan, or preflight time. It
also records the plan and policy fingerprints. The document is written to a
private same-directory temporary, flushed, and atomically renamed only after
every sample and drift check succeeds. Executor reports are published only
after exact workspace cleanup succeeds, except that explicit `--keep` retains
the validated manifest-owned workspace and records that choice before report
publication. A failed later sample or required cleanup leaves no final or
partial report.

The destination is create-exclusive. An existing ordinary single-link file is
preserved unless `--replace-report` is explicit, and its identity is revalidated
immediately before atomic replacement. The exact published path is printed.
There is no implicit append, rotation, time-based deletion, or report cleanup;
the operator chooses the path and retention period.

A quantitative claim must retain the report together with the source fixture
(including generator specification and seed when applicable), source/target
roots, empty-target/static-plan profile, operation mix, correspondence,
deletion/preflight/diagnostic flags, runtime/dependency versions, OS, concurrent
load, and storage/device topology. Relevant scaling axes are file count, size
distribution and total bytes, directory shape, operation mix, source/target
device topology, and repeat count; chunk or memory settings are axes only when
varied. The report records rig configuration and raw samples, but it cannot
discover every environmental receipt automatically.

### Verifier measurements

```powershell
.\.venv\Scripts\python.exe -m tools verifier E:\Corpus --mode baseline
.\.venv\Scripts\python.exe -m tools verifier E:\Corpus --baselines primed --repeat 5
.\.venv\Scripts\python.exe -m tools verifier E:\Corpus --seed-baselines --sidecar E:\RigEvidence\corpus.baseline.jsonl
.\.venv\Scripts\python.exe -m tools verifier E:\Corpus --baselines sidecar --sidecar E:\RigEvidence\corpus.baseline.jsonl
```

For `--mode verify`, the evidence-source matrix is:

| `--baselines` | Setup | Required result | Batch fixture anchor |
| --- | --- | --- | --- |
| `primed` (default) | one in-process baseline pass | `VERIFIED` | priming evidence |
| `sidecar` | prior `--seed-baselines` pass | `VERIFIED` | validated sidecar evidence |
| `synthetic` | deliberately wrong digest | `MISMATCHED` | setup scan |
| `none` | no prior evidence | `BASELINED` | first accepted sample |

Baseline mode always runs bare despite the parser's default baseline-source
value. Baseline and rebaseline modes require homogeneous `BASELINED` results;
when rebaseline is given an evidence source, that source still anchors its
fixture even though the new attestations are the measured output.
Synthetic mismatch is an intentional successful measurement because comparison
happens only after the full read-and-hash loop. Every other mixed, shortened,
modified, erroneous, or degraded result invalidates the sample. Incomplete
scans, unsupported entries, and canonical-path collisions are refused before
measurement. Outcome IDs and final item/byte totals must exactly cover the
selection. Priming requires exactly one applied attestation per scanned file.
Every measured scan must have the same canonical keys and stat subjects as its
setup evidence, or as the first sample when no setup evidence exists. Primed
and synthetic in-process anchors require exact `FileStat` equality; a sidecar
uses its declared portable or bound core matching predicate. This
closes the gap between a priming/sidecar scan and the timed pass instead of
allowing a shorter corpus to remain all-`VERIFIED`. For baseline, rebaseline,
and no-baseline verification, every repeated sample must also produce identical
operation-keyed content evidence, detecting same-stat content drift after the
first sample when the real hasher is active. `--null-hasher` deliberately makes
that content evidence constant for hash-cost isolation, so its source must stay
quiescent; stat and membership drift still refuse. Any detected fixture drift
invalidates the whole batch and suppresses its report.

Reader instrumentation remains enabled by default. Each accepted sample prints
open time, read time, and verifier time outside those calls; `--no-tap` removes
that split. Repeated verifier batches print N, minimum, median, and maximum run
time plus median sample throughput. Baseline preparation is labeled and timed
separately as setup, not silently counted as a sample. Reports retain that setup
receipt, and sidecar-backed reports include the explicit path, validation
counts, and stored identity mode.

### Verifier admission assessment — 2026-09-27

The verifier shares the executor's repeated native admission cost, with much
lower per-file multiplicity. This follow-up measured unchanged code at
`6de6d1c002fa0b9f22a4d76c25519b6d0dbfae8a` on the same reference machine and
read-only `F:\NamiSyncExecutorBenchSource` size bands described above. The native
unbuffered reader used 4 MiB chunks and `xxh3_128`; each band ran five timed
`tools verifier <band> --baselines primed --repeat 5` samples. Scanning, context
construction and the one-time baseline pass are outside `run_seconds`. This
is a single-volume read assessment, not another F:/G: copy measurement or a
controlled cold-cache experiment. Raw `verifier-*.json/log` and the temporary
`verifier_baseline.ps1`/`verifier_diagnostic.py` live beside the executor evidence
in ignored `build/executor-assessment-20260927/`.

| Corpus | Median run seconds | Min–max seconds | Median MiB/s |
| --- | ---: | ---: | ---: |
| 1,000 × 4 KiB | 3.652 | 3.575–3.772 | 1.07 |
| 512 × 128 KiB | 1.913 | 1.837–2.025 | 33.5 |
| 64 × 4 MiB | 0.311 | 0.307–0.317 | 822.6 |
| 4 × 128 MiB | 0.237 | 0.236–0.246 | 2,160.0 |
| 1 × 4 GiB | 1.926 | 1.862–1.956 | 2,126.3 |

All 25 samples returned exactly the expected verified items/bytes and recording
OK. Three later small-file `--no-tap` samples had median 3.287 s
(3.282–3.337 s). These were not interleaved controls: timing variation prevents
attributing their difference solely to instrumentation. The rig's open timer
covers native reader entry, excluding the engine's earlier admission; its read
timer covers iterator advancement, including a handle stat, buffer management
and byte materialization, not only the native read call. Outside-open/read time
therefore is not pure hashing overhead.

Separate synchronous Python/API wrappers measured one small-file pass at
3.196 s and one 4 GiB pass at 2.008 s, both fully verified. Counts below apply
to the 1,000-file pass; native API timings are measured directly rather than
inferred from cProfile self time. Parent timings overlap their children and
must not be added. Instrumented timing is diagnostic, not a predicted saving.

| Observation | Calls | Seconds |
| --- | ---: | ---: |
| `GetVolumePathNameW` | 4,000 | 1.1566 |
| `GetVolumeInformationW` | 1,000 | 0.0235 |
| `GetDiskFreeSpaceW` | 1,000 | 0.0205 |
| `ReadFile` | 1,000 | 0.5209 |
| Full root admission, inclusive | 1,000 | 0.9800 |
| Chain admissions, including those inside full admission | 2,000 | 1.0792 |
| Native API object construction/signature setup, inclusive | 1,000 | 0.1079 |
| Handle-stat snapshots, inclusive | 4,000 | 0.0786 |
| `GetFileInformationByHandleEx`, inside those snapshots | 12,000 | 0.0249 |
| `VirtualFree` | 1,000 | 0.1031 |

The four anchor lookups per readable file are two in full engine admission,
one in the reader's later chain admission, and one for sector geometry. Native
anchor lookup is the largest individually timed API cost here too. The 4 GiB
pass has the same four anchor calls and four handle snapshots, but 1,024 reads;
the setup tax is per file rather than per chunk. Root/child chain work also
scales with path depth; this shallow corpus does not quantify that slope.

Unlike executor, verifier already constructs and passes an immutable
`RootAuthority` in its run context: instrumentation counted no construction
during the timed file loop. There are still two selected-root validations per
readable item and repeat lexical normalization in the bound reader. Both
standalone verification and post-copy readback reach `_classify_subject` and
the same native reader, so the native findings apply to both paths; the timing
table measures standalone verification only.

Priorities and constraints for a future implementation:

- Apply the shared core admission work identified above: fewer anchor calls
  and potentially fresh root identity at access boundaries. Engine admission
  and reader admission currently enforce different protocol seams; combining
  them needs an explicit admission handoff that preserves custom-reader
  enforcement and the last check before opening. No cached successful admission
  across files, and no claim that current path checks make the later open atomic.
- Reuse the verifier reader's native bindings across files. Binding fixed API
  signatures is not filesystem evidence and requires no per-file refresh.
  Sector geometry should reuse an admitted anchor where valid; any longer-lived
  geometry reuse must be bound to volume identity, not merely a drive letter.
- Consider sharing the immediately consecutive native pre-yield and engine
  before-read handle snapshot. Native direct-reader rejection of directories
  and reparse files must remain. The third snapshot is inside `iter_chunks`,
  after `on_stream_start` can run external code; do not discard it solely from
  the count. The fresh after-read snapshot, opened-volume identity and final
  path-by-handle comparison have separate jobs and remain required evidence.
- Lower-priority candidates are one selected-root normalization per item and
  reader-lifetime aligned-buffer reuse. The measured buffer release cost makes
  reuse worth testing, but requires explicit close/error/cancellation ownership.
  Handle-stat consolidation is modest: all four snapshots together cost only
  0.079 s here, far below anchor lookup.

These are investigation findings, not changed [VERIFIER](VERIFIER.md) or
[DEFENSE](DEFENSE.md) contracts. No optimization variant was implemented or
benchmarked, and no throughput improvement is claimed.

### Preflight and scanner follow-up — 2026-09-27

Source inspection at `6de6d1c0` confirms that preflight shares the admission
mechanism. `preflight.observe()` already constructs authorities once per root
and deduplicates subjects by root ID and normalized relative path. Each
`LocalObservationFileSystem.stat()` nevertheless performs a full `admit_root`,
then selected-relative chain checks, root/candidate resolution and a final
no-follow leaf stat. A flat 1,000-COPY plan with distinct source and target
paths therefore has 2,000 subject admissions, two root observations and two
target admissions for free-space/reclaimable-temp observation: 2,004 full
admissions before any optional trash path. Each full admission has the same two
anchor lookups measured above. Reclaimable-parent volume observations can add
further native calls; this is not an exact whole-preflight API total. Parent,
prior-target and trash subjects make other operation mixes different.

This is a source-derived count, not a new preflight timing measurement. Executor
rig timing excludes its preflight setup, so that cost must not be added to or
subtracted from the reported execute medians. Shared core probe improvements
would reach preflight as well as executor and verifier. Pure derivation and
repeated root resolution deserve investigation, but per-subject freshness is
separate from immutable authority reuse. Nor are the two leaf observations
automatically interchangeable: the chain check precedes path resolution; the
final stat supplies the returned observation afterward. Consolidation must
preserve rejection before following a reparse target during resolution.

Scanner does not exhibit the same per-file full-admission pattern. Full scans
bracket enumeration with root/volume checks and discard observations on closing
drift; individual entries use enumeration and no-follow entry stats. Scoped
scans add selected-path ancestor checks. This source inspection supports leaving
scanner out of the current optimization priority, not a claim of measured
scanner throughput. Borrowing its batch observation boundary for preflight
would be a separate contract proposal, not permission to cache admission across
subject observations. No production, acceptance or safety contract was changed.

### Sidecars

Baseline persistence is separate retained input evidence, not benchmark output.
Both `--seed-baselines` and `--baselines sidecar` require an explicit `--sidecar
PATH`; the CLI never infers `<corpus>.baseline.jsonl`. A seed write uses a
same-directory temporary and create-exclusive atomic publication. Existing
sidecars are preserved unless `--replace-sidecar` is explicit. Replacement
captures the ordinary single-link destination identity before the potentially
long priming pass and revalidates that same occupant immediately before atomic
publication; a file swapped in during priming is preserved and refused.
Workspace `clean` never guesses or removes a sidecar.

Seeding is a distinct evidence-creation action. It runs exactly one untapped
baseline pass and rejects incompatible repeat, mode, baseline-source, tap, and
report settings instead of silently ignoring them. `--identity` and
`--replace-sidecar` apply only to seeding.

Loads require an explicit format and identity mode, exact row schemas without
duplicate JSON members, XXH3-128 evidence, complete key coverage, and a fresh
stat match through the same pure core predicate used by verifier classification.
The active `namisync-rig-baseline-2` format stores a bound Windows file index as
canonical `FileIndex128` decimal text, never a JSON number. Version-1 sidecars
are refused at the format boundary and must be reseeded explicitly.

`portable` identity compares kind, size, and mtime and survives relocation.
`bound` additionally requires volume serial and file index for every row; it
never silently falls back to portable matching. Relocation must preserve
`mtime_ns`.

### Isolating hash cost

`--null-hasher` consumes every chunk but returns a constant digest. With primed
baselines, both passes use that same hasher and still reach `VERIFIED`:

```powershell
.\.venv\Scripts\python.exe -m tools verifier E:\Corpus --baselines primed
.\.venv\Scripts\python.exe -m tools verifier E:\Corpus --baselines primed --null-hasher
```

Verifier sidecar plus `--null-hasher` is refused because a real sidecar and a
constant digest would create a misleading mismatch. `--no-tap` removes the
per-chunk reader timing when clean wall-clock measurements matter more than the
open/read split. The timing decorator forwards the authority-bound reader seam,
so enabling the tap cannot downgrade a reviewed native read to the unbound
custom-reader route. Its authority-bound subtype is used only when the wrapped
reader supports that protocol; the base tap preserves an unbound custom
reader's ordinary `open(root, path)` capability.

### Cache honesty

The verifier uses Windows unbuffered reads, so its numbers are cache-honest by
construction. Executor reads use the buffer cache; repeated reads of the same
source are warm and are not comparable to first-touch throughput. A static-plan
batch is specifically a buffered repeated-source/warm-profile observation; the
preparation reuse does not make it a cold or first-touch benchmark.

### Corpus generation and cleanup

```powershell
.\.venv\Scripts\python.exe -m tools generate E:\Corpus "2000@4KiB,200@1MiB,4@256MiB" --seed 7
.\.venv\Scripts\python.exe -m tools clean E:\Corpus --dry-run
.\.venv\Scripts\python.exe -m tools clean E:\Corpus
.\.venv\Scripts\python.exe -m tools clean E:\LegacyRigWork --force-all
```

Generation accepts a new or empty directory, or a directory carrying a valid
bound marker plus an exact output manifest. Each successful run publishes the
generated file and directory set into that manifest. Regeneration removes only
the validated recorded set, so the same seed and specification produce the same
complete tree; an unlisted descendant refuses replacement and is preserved.

Ordinary `clean` requires an existing valid marker and either an empty root or
an exact output manifest. It never creates or adopts a workspace merely because
the command was given a path. Reports and verifier sidecars are operator-owned
artifacts outside the root and are never guessed or removed by workspace
cleanup.

`--repeat` must be positive. Accepted iterations print their raw summary and a
repeated batch prints its aggregate. `--json PATH` writes the one atomic batch
report described above. Unsafe configuration or an invalid sample returns exit
code 2 with an actionable error and publishes no report.

### Measurement integration boundary

No logger or product-CLI integration is appropriate for the measurement
package. `INTERFACES.md` defines logging as a GUI-host facility under
`interfaces/web`, consuming GUI paths and capturing pywebview. Importing it into
the Python harness would invert the measurement boundary and could perturb
results through rotation or concurrent log writers. The standalone `gui.ps1`
does not import that package into the harness; it starts the existing headed
composition externally and uses that host's isolated development log.

Keep `python -m tools` separate from `nami-sync`: the latter is a shipped product
surface with lazy GUI imports and reviewed domain workflows, while the
measurement commands use fake persistence seams and destructive owned
workspaces. If distributing those commands is later required, prefer a separate
development entry point after an explicit packaging and workspace-safety review.

## History methods and observations

[HISTORY](HISTORY.md#policy-tuning-and-scale-gate) owns the window policy,
durability tradeoff and release criteria. The following historical
observations use their recorded Python/host profile and do not certify
current-source behavior. Raw historical benchmark output was not committed
as a compact JSON authority; retain its available original logs.

Current selected cases are `python -m tools performance history smoke --json
build/history-smoke.json` for a bounded diagnostic and `python -m tools
performance history release --json build/history-release.json` for the full
release fixture and its unchanged limits. Both reports retain every raw
transaction, item-page and event-page sample alongside derived statistics.
The release case uses the 50-run/1,000,000-item population below; the smoke
case uses two runs/96 items and cannot close the release criteria. A failed
release limit is a failed case, not a favorable diagnostic sample.

Use a fixture with 50 runs and 1,000,000 items,
including one 100,000-item run, and record:

- Windows build, CPU, storage, Python and SQLite versions;
- cold versus warm cache state;
- transaction count and window count;
- p50, p95, and maximum window-commit latency;
- peak pending event count and serialized bytes;
- 50-run summary latency and 256-row item/event page latency.

The 2026-08-05 baseline ran the then-current
`.\.venv\Scripts\python.exe tests\history_benchmark.py` on Windows 11
10.0.26200, Intel64 Family 6 Model 189 with 8 logical CPUs, Python 3.14.6, and
SQLite 3.50.4. The 650,465,280-byte fixture contained exactly 50 runs and
1,000,000 items, with one 100,000-item run. The full-range recording took
87.969 seconds over 3,919 transactions; commit latency was 7.969 ms p50,
25.237 ms p95, and 104.301 ms maximum. Peak retained state
was 256 events and 79,360 serialized bytes. A fresh-reader 50-run summary took
0.984 seconds and the immediate repeat took 0.652 seconds. Fresh-reader
item/event pages took 9.556/8.012 ms; full-range warm item pages were 10.686 ms
p50, 17.746 ms p95, and 37.898 ms maximum, while event pages were 9.800 ms p50,
13.995 ms p95, and 22.100 ms maximum. “Fresh reader”
means a new SQLite connection after fixture creation, not a forced cold OS
filesystem cache. All locked gates passed.

The 2026-08-06 rerun after sparse event-bound and official-watermark validation
used the same environment, fixture, and policy. Recording took 48.826 seconds
over 3,919 transactions; commit latency was 3.676 ms p50, 14.382 ms p95, and
204.203 ms maximum, with the same 256-event/79,360-byte retained peak. Summary
readback took 0.409 seconds on a fresh reader and 0.516 seconds immediately
afterward. Fresh-reader item/event pages took 3.650/5.092 ms; warm item pages
were 3.927 ms p50, 7.486 ms p95, and 8.861 ms maximum, while event pages were
3.614 ms p50, 6.163 ms p95, and 6.752 ms maximum. All locked gates passed; no
window-policy default changed.

The final 2026-08-08 history-v5 receipt rerun used the same million-item
fixture and 256-event/1-MiB policy after receipt/projection hardening. Recording
took 136.700 seconds over 3,919 transactions; commit latency was 20.899 ms p50,
44.491 ms p95, and 121.026 ms maximum, with retained state peaking at 256
events/79,360 bytes. Fresh and immediate-repeat 50-run summaries took
1.670/1.605 seconds. Warm item pages were 12.386 ms p50, 15.156 ms p95, and
16.256 ms maximum; event pages were 12.375 ms p50, 14.087 ms p95, and 14.818 ms
maximum. Audit remained OK for the ordinary fixture and every locked gate
passed; no window-policy default changed.

## Other measurement families

### Bridge transport custody

AB-8 changes the current `next_events` response to include one compact Python
task snapshot. A current-source observation must include snapshot construction,
byte admission and browser adoption; timing the retired browser reducer is not
the same endpoint. Rate/ETA estimates are product feedback based on monotonic
sink-acceptance samples, independent of drain cadence, not throughput
measurements. Existing historical JSON is unchanged;
it does not measure the new snapshot owner or certify its retained memory.
The functional AB-8 checks count bounded publication and retain the existing
large Plan window/detail witnesses without establishing a new speed target.

`python -m tools performance --list` lists the current optional diagnostic
cases; `python -m tools performance bridge-event installed --json
build/bridge-event.json` runs the bridge case. It stages driver and page assets from the
working tree but builds the measured product wheel from archived HEAD; the
report labels `driver_source` and `product_source` separately. The v5 fixture
decodes its 1–1,500 byte coordinates, checks item-free terminal facts, and
retains ordered ItemOutcome IDs as its independent item witness. Its bounded
native child publishes the first browser report failure before Close and keeps
partial sample and producer streams when cancellation ends the fixture early.
An incomplete or v4-only observation does not satisfy current event-v5
transport correctness or the frozen SH-G-8 custody claim. Use the unchanged
custody tests and their authority below for that gate.

The 2026-09-27 repair verification used archived product `639b2ea` and the
IR-BRIDGE working-tree driver. `build/admission-bridge-closeout-20260927/bridge-full-final.json`
records `status=complete`, `measurement_valid=true`, four valid sessions with
150 ordered reliable outcomes each, and no gaps or browser failures. Historical
`passed`/`event_passed` are false; this is endpoint completion, not new timing or
custody acceptance. The injected-report-failure receipt in the same directory
records an intentional rejection after five accepted batches, normal host exit,
the original error and report metadata, and a `raw_evidence` directory containing
failure/final milestones, authenticated samples and four unfinished producer
timing streams. Earlier failed receipts remain alongside the final evidence.

The frozen v1 [calibration](../tests/interfaces/web/sh_g_8_transport_calibration.json),
[ceiling](../tests/interfaces/web/sh_g_8_transport_ceiling.json) and
[holdout](../tests/interfaces/web/sh_g_8_transport_holdout.json) belong to
tested commit `56c50b43dc19090ad33af031891503bfec80599b` and the named
realistic transport corpus. Calibration-a measured 1,376,690 bytes/4,890
objects ordinary and 1,534,946 bytes/5,499 objects at the exact maximum
without Gap. The separately frozen ceiling is 1,966,080 bytes (1.875 MiB).
Independent holdout-b measured 1,351,794 ordinary and 1,513,014 exact-maximum
bytes, with three fresh runs below that ceiling. These results do not claim
complete-domain or current v5 transport memory containment. [BRIDGE](BRIDGE.md#evidence-and-ongoing-checks)
owns the accepted custody behavior and current gate status.

- [BRIDGE](BRIDGE.md#evidence-and-ongoing-checks) retains transport custody
  and behavior authority. Its event fixture uses four active tasks for 60
  seconds at 100 aggregate Progress and 10 reliable events per second;
  current-source timing remains open. The committed SH-G-8 custody JSON and
  validator have distinct frozen v1 provenance.
- [HISTORY](HISTORY.md) retains query behavior and limits; use its named
  fixture and query-method evidence without merging it with Plan timings.
- [TOOLS](TOOLS.md#performance-drivers) owns the executor/verifier driver
  structure and isolated harness boundary. Their throughput observations do
  not certify Plan, bridge or release resources.
- [INTERFACES](INTERFACES.md#sh-g-release-criteria) retains SH-G-15 cold-start
  and repeated/long-workload release resource acceptance. It has no numeric
  budget or acceptance artifact yet.

Raw child logs, screenshots, installed wheels, failure context and generated
reports under ignored `build/` remain at their recorded paths, including
`build/m1-7/evidence/p9-full-20260916/` and
`build/m1-8-archive-20260924/evidence/`. Committed JSON preserves selected
samples and authority, not necessarily every native or visual artifact.
Ignored `build/` is not durable archival storage; preserve existing raw
directories and consider a separately managed archive before cleanup of
irreplaceable evidence.
