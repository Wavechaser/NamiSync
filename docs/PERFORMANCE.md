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

## Cold inventory projection acceptance method

PRESENTATION owns the retained base 3 s / information-heavy 6 s maxima. The
inventory maxima remain fixed acceptance criteria; optional Plan/UI diagnostics
do not replace or close this gate. The dedicated
`python -m tools.performance.inventory --check` command validates its
full deterministic fixtures without collecting timing. Acceptance collection
uses `--collect --profile PATH` only after confirming the actual reference
profile above, AC power and absence of unrelated sustained workload. The profile
JSON records `captured_at`, OS name/build, CPU, physical/logical core counts,
memory GiB, repository device and explicit `reference_profile_confirmed`,
`ac_power` and `no_unrelated_sustained_workload` facts. A changed or unverified
profile needs a DEFENSE §7 disposition before it can close acceptance.

The inventory corpus uses seed `0x4E414D49`, 100,000 typed file rows and 20,000
synthetic folders, five files per folder, for 120,000 displayed rows excluding
the internal root. Raw sizes are 7 and mtimes 11; every fifth row retains typed
verify-provenance attestation, giving 20,000 evidence rows. The information-heavy
variant adds 120,000 typed warnings with indexed paths, bounded indexed detail
and a stable ScanWarningCode cycle, for 240,000 displayed rows. These populations
are fixture facts, not a new total-row admission wall.

Each fresh child imports the product, constructs complete input tuples and runs
`gc.collect()` before the clock. One interval surrounds only the real
`build_inventory_projection` call, including its tree, indexes, rollups and
validation. Startup, input generation, sibling view sorting, window/detail work
and post-build correctness are outside it. GC remains enabled at its recorded
normal setting. Post-build checks cover every subject/warning, exact populations,
current/attested evidence, aggregate counts/bytes, warning attachment and index
exclusion, plus independent path-derived first/middle/last folder membership.
Wrong or unfinished construction invalidates the sample regardless of elapsed time.

The collector launches five sequential fresh child processes per case, one cold
sample each. Raw JSON and stdout/stderr record launch argv, repository cwd,
invocation identity, Popen-launched and child/parent process ids, sample membership, nanoseconds,
fixture seed, runtime/GC, candidate revision/dirty context and source SHA-256
bindings. A direct child's id matches the launched id and its parent is the
collector; a Windows venv redirector child's parent matches the launched id.
Process ids may be reused; matching launch receipts substantiate actual
collector launches without claiming cryptographic protection. Per-case maximum
is the predeclared statistic; minimum/maximum dispersion accompanies it. The
separate `python -m tools.performance.validate_inventory RAW_JSON` checker
requires all ten matching samples and compares maxima with 3/6 seconds. Its
acceptance checks remain active under optimized Python; the collector requires
a normal interpreter so fixture assertions cannot disappear.

The finite gating source corpus is the collector/fixture and separate checker;
`workflows/inventory_projection.py` and `node_tree.py`; `core/models.py`,
`evidence.py`, `integrity.py`, `pathing.py`, `scalars.py` and `review.py`; and
`db/repositories.py` for row facts and derived verification state. These own the
construction, type, scalar/path or property calls exercised by this interval.
Unrelated facade/runtime/executor imports, Plan sorting and later view work are
outside it; their edits alone do not invalidate cold construction evidence.
Changed gating files, fixture, producer/checker/driver, Python/dependencies or
accepted machine/profile require fresh affected samples.

This local, predeclared named-reference criterion uses Tier 2 under DEFENSE §7:
retain committed compact raw/validation JSON under `tests/interfaces/web/` and
raw child logs under ignored `build/m1-9-20261001/`. Every run has a fresh exclusive
directory; failures remain incomplete and neither reports nor validator results
are overwritten. Samples apply only to the recorded profile and five children,
without universal latency, memory or complexity claims. No acceptance samples
are claimed merely by adding this method or passing correctness-only controls.

### Inventory projection result — 2026-10-01

The coordinated quiet reference-profile run passed both fixed maxima:
base **1.9712401 s** and information-heavy **2.8123806 s**, each the maximum
of five fresh child samples. The observed hardware, AC power, Python and SQLite
match the reference profile above. The [raw samples](../tests/interfaces/web/m1_9_inventory_cold_raw.json)
bind the exact construction/driver/checker bytes, and the [separate validation](../tests/interfaces/web/m1_9_inventory_cold_validation.json)
records their passing verdict. The candidate is based on `ec3865c` with the
explicit working-tree source hashes in the receipt; unrelated read-surface
changes were present but are outside the timed dependency corpus.

Raw child logs remain under
`build/m1-9-20261001/measurement-inventory-cold-20261001T115350Z-48927bf0/`.
An earlier incomplete attempt rejected a Windows venv redirector's process
identity before sample admission. It remains failed evidence; the corrected
collector/checker were independently reviewed and tested with a real untimed
launch before this complete run. No wider runtime or memory claim follows.

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
[M1_PLAN](M1_PLAN.md#root-admission-optimization--2026-09-28) records that goal
and the round's delivery.
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

### Preflight invocation holds — 2026-09-28

After the corrected core/executor commit `8cdd669`, preflight owns confirmed
root holds and checks current handle attributes before cached admission reuse.
The candidate includes the earlier core call reductions as well as this consumer
change; comparison with baseline `b8baf42d` does not isolate their timing effects.

The identical `resume/measure_preflight.py` driver runs from each checkout,
prepares a 1,000 × 4 KiB COPY plan using the preserved F: source and the same
empty G: target, then performs three fresh observations and judgments. It never
executes the plan. Source scan equality, exact target emptiness and manifest
equality are checked outside timed samples; successful exact-empty teardown
removes the owned fixture. Samples are serialized after broad/native gates;
there is no cache eviction or control of unrelated desktop activity.

| Observation, seconds | Baseline min / median / max | Candidate min / median / max |
| --- | --- | --- |
| Filesystem observation | 2.261 / 2.722 / 2.779 | 0.549 / 0.551 / 0.587 |
| Pure judgment | 0.0100 / 0.0101 / 0.0137 | 0.0095 / 0.0098 / 0.0117 |

A separate identical wrapper counts project ctypes Win32 binding calls only
inside `observe`; its timing is excluded. Every counted sample agrees:

| Call per 1,000-file plan | Baseline | Candidate |
| --- | ---: | ---: |
| `GetVolumePathNameW` | 4,009 | 3 |
| `GetVolumeInformationW` | 2,005 | 3 |
| Root opens / closes each | 0 | 2 |
| Final-path confirmation | 0 | 2 |
| Current handle basic information | 0 | 2,002 |

All observations and verdicts pass. Receipts under
`build/root-admission-optimization-20260928/resume/` are
`preflight-baseline-timing.json`, `preflight-guarded-timing.json`,
`preflight-baseline-call-counts.json` and `preflight-guarded-counts.json`, with
driver/import/manifests and associated counted reports. The ordinary gate passes
5,480 tests; the unchanged 46-group differential retains complete worlds/verdicts,
explicit prevented-swap controls and strict mixed-source fallback.

Separate F:→K: observations on exFAT `BA1F1F45` also pass with the candidate
counts above and successful source/empty-target checks. These ran alongside the
ordinary gate and are functional evidence only, not timing observations or
exFAT copy acceptance. Receipts are `preflight-guarded-exfat-*`; the existing
executor handle-identity compatibility issue remains separate in BUGS.

### Verifier invocation holds and geometry — 2026-09-28

After preflight `4263b12`, the verifier holds its root through each invocation
and guards reused admission with current handle attributes. The comparison with
`b8baf42d` includes earlier core improvements; it does not isolate their effect.
A second atomic outcome queries sector geometry on the opened file handle,
retaining fresh pathname fallback when that query is unavailable or zero.

The same `verifier/measure_verifier.py` runs from both checkouts on the preserved
F: 1,000 × 4 KiB corpus. It primes real evidence outside timing, then measures
three fresh VERIFY invocations through the standard native reader tap. Scanning,
authority/selection construction and priming are outside the measured runner.
All 1,000 outcomes are verified/applied with successful recording, 4,096,000
actual read bytes and matching command/outcome IDs. Source FileStat observations
and product/tools manifests match before/after. Samples run serially after the
gates and native captures; unrelated desktop activity remains uncontrolled.

| VERIFY runner, seconds | Minimum | Median | Maximum |
| --- | ---: | ---: | ---: |
| Baseline | 3.827 | 3.885 | 3.940 |
| Invocation holds | 1.964 | 1.998 | 2.002 |
| Holds and handle geometry | 1.267 | 1.512 | 1.551 |

A separate one-invocation wrapper counts project ctypes bindings only inside
VERIFY. Its timings are excluded. Per 1,000 files:

| Call | Baseline | Invocation holds | Holds and handle geometry |
| --- | ---: | ---: | ---: |
| `GetVolumePathNameW` | 4,000 | 1,001 | 1 |
| `GetVolumeInformationW` | 1,000 | 1 | 1 |
| Opens / closes / final paths, each | 2,000 | 2,001 | 2,001 |
| File handle information | 12,000 | 12,000 | 12,000 |
| Current root basic information | 0 | 1,999 | 1,999 |
| Handle sector information | 0 | 0 | 1,000 |
| Pathname sector query | 1,000 | 1,000 | 0 |
| Reads / allocations / frees, each | 1,000 | 1,000 | 1,000 |

The file-information calls still cover four snapshots per file; the added root
queries and handle-sector information are separate. These are
diagnostics, not a latency gate or executor-throughput claim. Receipts under
`build/root-admission-optimization-20260928/verifier/` are
`baseline-verify-timing.json`, `candidate-verify-timing.json`, `geometry-verify-timing.json`,
their `*-verify-counts.json`
and their counted reports, with frozen driver/import/source/product provenance.
The hold gate passed 5,502 ordinary tests; geometry passes 5,514. Both pass 12
imports, unchanged oracle 30 × three and guard scan; the same qualified 67-group
differential has no unexpected differences. Geometry timings run after its gate;
the unchanged baseline/hold receipts remain diagnostic references, not randomized
or fresh-process causal measurements.
No exFAT verification or identity-compatibility claim is made.

**Executor continuation profile.** After these verifier measurements, a separate
caller-thread cProfile sample wraps only `execute` on 1,000 × 4 KiB F:→fresh G:.
Copies, native readback, source observations, product manifests and manifest-based
cleanup pass. Its instrumented 32.4 seconds is not a throughput sample. It records
160,030 extended-path conversions, 435,084 absolute-spelling validations, 26,000
physical resolutions and 9,000 `_stat_path` calls. Inclusive costs overlap;
worker threads are outside this profile. Repeated pure path work and leaf stat
remain measured leads, not permission to retire physical/descendant checks.
Raw `resume/executor-after-verifier-profile.{prof,txt,json}` and `-run.json`
retain the driver/input provenance and complete rig report.

**Executor single leaf observation.** The checked no-follow snapshot now also
supplies leaf metadata. Three serialized uninstrumented samples on the same
1,000 × 4 KiB F:→G: fixture measure 12.365 seconds median (11.934–13.104),
0.316 MiB/s, versus the prior guarded 15.271 seconds. All copies/readbacks and
source rechecks pass; rig-owned targets are removed. This remains a diagnostic
comparison without randomized order or cache eviction, below the 1 MiB/s goal.
Separate project-ctypes counts remain unchanged: 6,002 anchor and volume calls
each, 2,002 opens/closes, two final-path queries and 31,998 information queries.
The caller-thread profile records 17,006 `nt.stat` and 16,000 `nt._path_lexists`
calls, versus 20,006 and 25,000 before consolidation: 12,000 fewer observations.
Physical resolutions remain 26,000. Extended-path conversions rise from 160,030
to 163,030 because missing leaves now reach the checked observation; pure-path
reuse remains a separate optimization. Instrumented time is not throughput.
Receipts are `resume/executor-single-stat-{timing,counts,counted}.json` and
`resume/executor-single-stat-profile.{prof,txt,json}` plus `-run.json`; profile
input manifests match.

**Bounded executor path reuse.** On the same serialized fixture, three samples
measure median 10.757 seconds (10.656–11.819), 0.363 MiB/s. The preceding leaf-only
median is 12.365 seconds. Copies, native readbacks, source rechecks and scoped rig
cleanup all pass. Separate caller-thread profiles show extended conversions
163,030→22,025, spelling validations 441,084→90,074 and lexical conversions
77,018→8,018. Actual observations remain 17,006 `nt.stat`, 16,000 existence probes,
26,000 physical resolutions and the unchanged project-ctypes counts above.
This isolates the count reduction to pure path work; it does not establish a
randomized causal speedup or satisfy the 1 MiB/s goal. Receipts use the same
`resume/executor-path-cache-` timing/counts/counted/profile suffixes as the leaf
outcome; the separate profile summary is diagnostic, and input manifests match.

**Single-lstat descendant walks and final breakdown.** Three serialized samples
measure median 9.684 seconds (9.155–10.471), 0.403 MiB/s, versus the preceding
10.757 seconds. Every copy/readback and source recheck passes, and all rig-owned
targets are removed. Separate profiles show existence probes 16,000→3,000 and
`nt.stat` 17,006→23,006 as unavailable descendants now reach the checked lstat:
7,000 fewer observations in this step, 19,000 fewer across leaf and descendant
consolidation. Actual extended conversions stay 22,025 despite helper calls
rising by 6,000; the bounded cache absorbs that duplicate pure work. Project-
ctypes counts remain unchanged. Receipts use `resume/executor-descendant-stat-`
with timing/counts/counted/profile suffixes; profile input manifests match.

The goal remains unmet. Remaining caller-thread profile leads are 26,000 physical
resolutions (4.326 inclusive seconds), 6,000 leaf volume observations (3.822) and
90,074 absolute-spelling validations (3.610). Inclusive times overlap and are
instrumented; do not sum them or subtract them from uninstrumented throughput.
Each leaf volume observation currently performs one fresh anchor and one fresh
volume query; none is a duplicate within that observation. Replacing these with
held-root facts and dropping the two held-path physical resolutions were explicitly
authorized in the resumed round. Other guard retirements are not inferred from
these measurements.

**String-only cache eligibility.** Three serialized samples on the same fixture
measure median 7.756 seconds (7.519–7.851), 0.504 MiB/s, versus 9.684 seconds.
All 1,000 copies and readbacks per sample, source rechecks and scoped cleanup
pass. Separate counts retain 6,002 anchor and volume queries each, 2,002 opens
and closes, two final-path queries and 31,998 handle-information queries.
The caller-thread profile retains 23,006 `nt.stat`, 26,000 physical resolutions,
6,000 leaf volume observations and 22,025 actual extended conversions. Receipts
use `resume/executor-cheap-cache-` timing/counts/counted/profile suffixes; inputs
match before and after. Instrumented runs are diagnostic, not timing authority.

**Leaf volume from the checked stat.** Three same-fixture serialized samples
measure median 5.383 seconds (5.332–5.387), 0.726 MiB/s, versus 7.756 seconds.
All copies/readbacks, source checks and manifest-scoped cleanup pass. Separate
counts show anchor and volume queries each falling from 6,002 to two; opens,
closes and final-path queries stay 2,002/2,002/two. Handle-information queries
rise from 31,998 to 37,998 because stat-derived volume reuse checks current held
attributes. Receipts use `resume/executor-stat-volume-` with the same timing,
counts, counted and profile suffixes. The profile remains diagnostic; its
dependency manifests match. These sequential observations are not a randomized
causal estimate, and the 1 MiB/s goal remains unmet.

**Held-root physical-resolution removal.** Three serialized samples measure
median 3.387 seconds (3.370–3.388), 1.153 MiB/s, versus the preceding 5.383
seconds. The goal is exceeded on this fixture, not promoted into a release
gate. Every sample completes 1,000 copies and native readbacks, preserves the
source and cleans the exact rig-owned target set. Separate caller-thread
profiles show 26,000 physical-resolution calls falling to zero; stat calls
remain 23,006, and runtime root revalidation still runs 27,000 times. Project-
native counts remain two anchor/two volume queries, 2,002 opens/closes, two
final-path queries and 37,998 handle-information queries. Receipts use
`resume/executor-held-resolve-` timing/counts/counted/profile suffixes, with
matching input manifests. These are sequential same-fixture observations;
instrumented runs remain separate from timing authority.

**Historical instrumentation and fast-path eligibility.** Before result 7,
method-wrapping stage timers could change the path being measured. Replacing methods checked by the
resolve or stat-derived leaf-volume selectors, even through `functools.wraps`,
made the corresponding selector use its custom-method fallback. Such timings characterize that
wrapped adapter, not the default production shortcuts. Root diagnostics showing
`held=true` attest the root hold; they do not prove that both resolve and leaf
volume shortcuts ran. Result 7 removes method-identity selection; instrumentation
must still be kept separate from uninstrumented timing, and historical receipts
remain bound to their original code and drivers.

For current diagnostics, use a sampling/call profiler or count the module
physical resolver and native volume bindings. Method wrappers no longer select
another admission sequence, but their timing overhead still matters. A combined native regression
checks the normal production stat/resolve composition after held admission:
correct file evidence, zero physical resolutions and zero leaf-volume probes.
These finite call assertions detect lost shortcut selection; they are not a
throughput gate. Collect throughput separately without instrumentation. The
historical timings above remain bound to their recorded inputs and drivers.

### User rerun after clearing source-drive contention — 2026-09-29

The user reported that F: was occupied during the finishing measurements below.
Those contended historical endpoints do not establish a performance regression.
The user's subsequent rerun supplied the medians below. HEAD is the user's
label; sample counts and ranges were not supplied with this table.

| Band | HEAD median (user label) | `23589bd` median | `db05e317` |
| --- | ---: | ---: | ---: |
| 1,000 × 4 KiB | 3.150 s (1.24 MiB/s) | 3.627 s | 7.99 s |
| 512 × 128 KiB | 1.640 s | 1.958 s | 4.25 s |
| 64 × 4 MiB | 0.373 s | 0.372 s | 0.64 s |
| 4 × 128 MiB | 0.297 s | 0.304 s | 0.31 s |
| 1 × 4 GiB | 1.956 s (2,095 MiB/s) | 2.004 s | 1.96 s |

The raw earlier runs remain below for chronology and correctness/readback
evidence. Their throughput-goal observations describe those runs, not a stable
regression attributable to the changes. The target-check follow-up is measured
separately after correctness verification.

### Integrated direct target writes — 2026-09-30

Result 8 implements the user-selected blanket 8 MiB threshold across device
types. Five serial samples per original F:→G: band use the production executor
with buffered source reads. All 25 executions and readbacks pass, with recording
OK, zero final reservations and stable source/product/tools/tests/driver hashes.
The three smaller bands report only buffered writes; the two larger bands report
only direct writes with no fallbacks. Aligned backing allocations remain within
32 MiB. The rig removes every owned target and sidecar.

| Band | Median [min–max], s | MiB/s | Result 7 median, s |
| --- | ---: | ---: | ---: |
| 1,000 × 4 KiB | 2.789 [2.557–2.902] | 1.401 | 3.341 |
| 512 × 128 KiB | 1.474 [1.322–1.581] | 43.428 | 1.740 |
| 64 × 4 MiB | 0.351 [0.328–0.385] | 728.517 | 0.356 |
| 4 × 128 MiB | 0.129 [0.127–0.137] | 3,965.116 | 0.290 |
| 1 × 4 GiB | 0.909 [0.778–1.135] | 4,504.627 | 1.924 |

Only the 4 MiB band overlaps its predecessor's range. Small-file backend/outside
medians are 0.106/2.683 s; the 4 GiB split is 0.904/0.006 s. Separate medians
need not sum to the total. The 4 KiB goal of 1.6 MiB/s remains unmet; per-file
work outside the copy backend dominates. The 4 GiB median is 52.7% shorter,
but these sequential historical endpoints do not isolate causality. All five
samples remain, including the 1.135 s large-file tail. Repeated-source results
are not cold-cache ceilings, other-device throughput, SQLite or GUI measurements.

Evidence prefix: `build/executor-simplification-20260929/measurements/`
`result8-b9c4ad3e-20260930-201114-989e90d9`. Before/after physical hashes bind the
uncommitted candidate on `b9c4ad3`; predecessor receipts separately identify
accepted result 7 (`878f15e`). The task's `five_band_result8.ps1` and
`five_band_result8_receipt.py` retain the original five-band procedure and add
mode/fallback checks. The earlier threshold sweep below remains diagnostic;
it does not select device-specific shipping policy.

### Direct-write threshold probe — 2026-09-30

The user's subsequent implementation decision is a blanket 8 MiB threshold
across device types, with no volume/model discrimination. The recommendations
below remain the experiment's observations; M1_PLAN owns the chosen policy.

After consolidation was reviewed and committed as `878f15e`, a standalone
Win32 helper compared buffered and `FILE_FLAG_NO_BUFFERING` target writes.
No production writer, pipeline or threshold was changed. These are Tier 0
diagnostic recommendations for the measured devices, not class-wide rules or
integrated executor throughput claims.

**Method.** F: (a separate SN850X) supplied read-only prefixes of the existing
4 GiB source. Each trial warmed that prefix, then timed target create/allocation,
buffered sequential source read, `xxh3_128`, synchronous QD1 writes, exact EOF
and file flush. Both modes used identical aligned buffers, chunk bands and the
existing allocation policy from 8 MiB. Geometry came from native handle storage
information; direct tails were padded privately and truncated on the same
handle before flushing. Untimed unbuffered readback checked exact length and
digest. This excludes metadata/publication/directory flush, recording, pipeline
overlap and pool setup. It does not measure cold-source reads or sustained SLC
cache exhaustion. Source and complete script/product dependency hashes matched
before/after every run.

The primary grid was 2/4/8/16/32 MiB on G/H/E/J/L, six balanced AB/BA pairs per
cell. Device order rotated and size order reversed between rounds. The recorded
criterion, set before measurement, was at least five of six direct-faster pairs
and median paired elapsed-time saving at least 5%, sustained at larger sampled
sizes. Single points at the upper edge do not establish a sustained boundary.
Only observed crossover brackets were refined (G at 6 MiB, L at 24 MiB).

| Target | 2 MiB | 4 MiB | 8 MiB | 16 MiB | 32 MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| G: SN850X | +36.6% (6/6) | +14.6% (4/6) | +34.8% (6/6) | +30.0% (6/6) | +31.7% (6/6) |
| H: SN550 | +18.7% (6/6) | +18.3% (4/6) | +30.5% (6/6) | +25.2% (5/6) | +6.4% (4/6) |
| E: Optane 905p | +5.7% (6/6) | +12.6% (6/6) | +27.1% (6/6) | +19.3% (6/6) | +26.9% (6/6) |
| J: HC550 HDD | −30.2% (0/6) | −2.4% (3/6) | −3.2% (3/6) | +2.8% (5/6) | −2.1% (3/6) |
| L: Samsung T7 | +12.9% (5/6) | +3.2% (3/6) | +10.6% (5/6) | +8.9% (4/6) | +14.3% (6/6) |

Cells show median **paired** saving and direct-faster pair count. They are not
the percentage difference between independently computed mode medians. Positive
values favor direct writes; meeting the percentage alone is insufficient.

| Target | Recommendation for future integration | Evidence and bound |
| --- | --- | --- |
| G: SN850X | Direct from 6 MiB | Refinement: +35.8%, 6/6; buffered/direct median 5.780/3.813 ms. All 8–32 MiB cells qualify. This is the smallest sustained sampled candidate, not a precisely located physical crossover. |
| E: Optane 905p | Direct from 2 MiB | Every primary cell qualifies; 2 MiB medians 2.167/2.008 ms. The crossover could be below 2 MiB; this sweep does not establish it, and the lowest-size margin is modest. |
| H: SN550 | Keep buffered | No sustained qualifying suffix: the 32 MiB cell wins only 4/6 pairs. |
| J: HC550 HDD | Keep buffered | No primary cell meets both criteria. |
| L: Samsung T7 | Keep buffered | 24 MiB refinement wins 0/6, paired saving −18.7%. A qualifying 32 MiB endpoint alone does not establish a stable threshold. |

L's 24 MiB timing is notably variable: buffered median 69.751 ms
[48.985–340.994], direct 331.576 ms [49.983–378.840]. All observations remain;
no favorable rerun or sample exclusion replaced them. The experiment does not
isolate the cause. H/L may benefit under a different workload, but this finite
probe does not justify enabling them. Do not infer a universal SSD threshold
or add device classification machinery from these five physical devices alone.
The future integrated implementation must validate its chosen buffering,
concurrency and finishing costs; this probe determines candidates, not its
speed or correctness acceptance.

**Evidence.** The G-only pilot passed 12 timed copies and two tail witnesses;
it validated the helper and is not pooled into the primary estimate. The primary
sweep passed 300 copies and ten 8 MiB+123-byte tail witnesses. Two refinements
passed 24 copies and four tail witnesses. All 336 copies and 16 tails had exact
readback, unchanged source/dependencies and exact owned-file/directory cleanup.
Raw samples, per-mode ranges and paired summaries remain under
`build/executor-simplification-20260929/ceilings/`:

- `threshold-baeeeab32bd6495ca4a5f75799619bbe/`: pilot.
- `threshold-d230a636d6fc4f38b79e20d003c59b93/`: primary grid.
- `threshold-0dfc0f6a45f1463a9ea6cf4feacd4fad/`: G 6 MiB refinement.
- `threshold-09c326775f964b919f8e4eccac9ed1cf/`: L 24 MiB refinement.

The immutable helper copy is `direct_write_threshold-reviewed-878f15e.py`
(SHA-256 `58ce54f72d0b330734449a6a120d29541dde5990eb95ea4d0366360e5f63f63f`).
`threshold-device-profile-20260930.json` records actual drive/model mappings;
`summarize_threshold.py` reproduces `threshold-observations-878f15e.json` from
raw receipts, checking pairs, allocation parity, hashes, readbacks and cleanup.

### Single held-root dispatch — 2026-09-30

Result 7's frozen candidate on `6157226` passed 331 native/runtime and 5,699
ordinary tests, imports, unchanged three-run oracle and the fixed 67-group
differential before measurement. All 25 serial executions/readbacks passed,
with recording OK, zero reservations, stable source/dependencies and exact
owned-target/sidecar cleanup.

| Band | Median [min–max], s | MiB/s | Result 6 median, s |
| --- | ---: | ---: | ---: |
| 1,000 × 4 KiB | 3.341 [3.242–3.873] | 1.169 | 3.211 |
| 512 × 128 KiB | 1.740 [1.710–3.611] | 36.774 | 1.682 |
| 64 × 4 MiB | 0.356 [0.332–0.614] | 719.644 | 0.348 |
| 4 × 128 MiB | 0.290 [0.286–0.319] | 1,763.455 | 0.302 |
| 1 × 4 GiB | 1.924 [1.883–2.294] | 2,128.908 | 1.999 |

Every predecessor range overlaps; this establishes no throughput gain or
regression. All samples remain, including the slow 128 KiB tail. Small-file
backend/outside medians are 0.413/2.928 s; the 4 GiB split is 1.428/0.646 s.
Separate medians need not sum to the total. These repeated-source buffered
runs are neither cold-cache/device ceilings nor direct-write threshold probes.
Evidence prefix: `build/executor-simplification-20260929/measurements/`
`result7-6157226f-20260930-170339-3d6968b5`; predecessor receipts identify result 6.

### Held-root path composition — 2026-09-30

Result 6's frozen candidate on `d43f832` passed 343 native/runtime tests and
5,711 ordinary tests, imports, unchanged three-run oracle and the fixed
67-group differential before measurement. All 25 serial executions/readbacks
passed with recording OK and zero reservations. Source and dependency manifests
stayed fixed; the rig removed its owned targets and sidecars.

| Band | Median [min–max], s | MiB/s | Result 5 median, s |
| --- | ---: | ---: | ---: |
| 1,000 × 4 KiB | 3.211 [3.144–3.274] | 1.217 | 3.222 |
| 512 × 128 KiB | 1.682 [1.669–1.944] | 38.058 | 1.685 |
| 64 × 4 MiB | 0.348 [0.340–0.397] | 735.772 | 0.341 |
| 4 × 128 MiB | 0.302 [0.299–0.312] | 1,696.785 | 0.296 |
| 1 × 4 GiB | 1.999 [1.791–2.060] | 2,048.743 | 1.981 |

All predecessor ranges overlap; this establishes no throughput lift. Small-file
backend/outside medians are 0.412/2.799 s; the 4 GiB split is 1.242/0.743 s.
Separate medians need not sum to the total. Every sample is retained; buffered
repeated-source measurements are not cold-cache/device-ceiling evidence.
Evidence prefix: `build/executor-simplification-20260929/measurements/`
`result6-d43f8324-20260930-133019-7ae09623`; its predecessor comparison points to
result 5's physical candidate and accepted `d43f832` separately.

### Own-effect version recognition — 2026-09-30

Result 5's frozen candidate on `8b2b00e` passed 5,714 ordinary tests, 27 focused
checks, imports, the unchanged three-run oracle and fixed 67-group differential
before measurement. Five serial samples per original F:→G: band all completed
with recording OK, exact readback and zero reservations. Source and dependency
manifests stayed fixed; the rig removed its owned targets and sidecars.

| Band | Median [min–max], s | MiB/s | Previous target-consolidation median, s |
| --- | ---: | ---: | ---: |
| 1,000 × 4 KiB | 3.222 [3.130–3.804] | 1.212 | 3.134 |
| 512 × 128 KiB | 1.685 [1.629–3.619] | 37.993 | 1.641 |
| 64 × 4 MiB | 0.341 [0.337–0.640] | 751.398 | 0.351 |
| 4 × 128 MiB | 0.296 [0.293–0.321] | 1,730.414 | 0.303 |
| 1 × 4 GiB | 1.981 [1.792–2.148] | 2,067.759 | 2.011 |

All ranges overlap the predecessor; no causal throughput lift is established.
Small-file backend/outside medians are 0.421/2.801 s; the 4 GiB split is
1.293/0.758 s. Separate medians need not sum to the total. Every sample is
retained; these buffered repeated-source observations do not establish cold-cache
or device ceilings. Small-file and large-copy headroom goals remain open.
Evidence prefix: `build/executor-simplification-20260929/measurements/`
`result5-8b2b00e4-20260930-130559-e544fed6`; its predecessor comparison binds the
earlier target-consolidation receipt separately to accepted `eb18611`.

### Target-check consolidation follow-up — 2026-09-29

Measured the frozen candidate on documentation commit `9c96893` after the
5,704-test native ordinary run, reviewed deletion-only oracle classification
and fixed starting-baseline differential. Five serial samples in each original
F:→G: band used normal metrics and native readback. All 25 executions/readbacks
passed with recording OK and zero reservations. Product/rig/test/driver and
source manifests stayed fixed; the original 1,587-entry source was unchanged,
and all owned targets/sidecars were removed.

| Band | Candidate median [min–max], s | MiB/s | User-reported pre-follow-up median, s |
| --- | ---: | ---: | ---: |
| 1,000 × 4 KiB | 3.134 [3.092–3.516] | 1.247 | 3.150 |
| 512 × 128 KiB | 1.641 [1.626–1.700] | 38.992 | 1.640 |
| 64 × 4 MiB | 0.351 [0.338–0.453] | 728.387 | 0.373 |
| 4 × 128 MiB | 0.303 [0.296–0.332] | 1,691.124 | 0.297 |
| 1 × 4 GiB | 2.011 [1.810–2.082] | 2,036.859 | 1.956 |

These results are close to the user's separate rerun. They do not isolate a
throughput gain from the two removed checks. The older contended finishing runs
are not a causal comparison. Small-file backend/outside medians are
0.405/2.728 s; the 4 GiB split is 1.453/0.440 s. Separate medians need not sum to
the total median. No sample was discarded; these buffered repeated-source
observations do not establish cold-cache/device ceilings. The non-gating
small-file goal and large-copy headroom goal remain open.

Evidence prefix: `build/executor-simplification-20260929/measurements/`
`target-9c96893b-20260929-191353-d421178a`. The existing predecessor comparison
retains the contended `result3b-84ce0fb2-20260929-175649-85162057` receipt and its
accepted `d444a6a` attribution for chronology, not causal performance judgment.

### Source-check consolidation — 2026-09-29

The first executor-simplification candidate on `dadc1fe` reuses fresh-copy
source fidelity and removes source admissions with no later source access.
Its exact precommit product/tool/test/driver hashes and status match before and
after measurement; the original 1,587-entry source manifest is unchanged.
The existing five F:→G: bands ran serially, five samples each, with normal rig
metrics and native readback. All 25 executions/readbacks completed with recording
OK and zero payload reservations; manifest-owned teardown removed every target
and sidecar. Timings cover executor calls, not preparation or readback.

| Workload | Candidate median [min–max], s | MiB/s | Time versus latest `23589bd` |
| --- | ---: | ---: | ---: |
| 1,000 × 4 KiB | 3.358 [3.262–4.044] | 1.163 | −7.4% |
| 512 × 128 KiB | 1.775 [1.681–3.619] | 36.049 | −9.4% |
| 64 × 4 MiB | 0.349 [0.345–0.648] | 732.733 | −6.2% |
| 4 × 128 MiB | 0.316 [0.307–0.337] | 1,617.852 | +4.0% |
| 1 × 4 GiB | 2.135 [1.976–2.335] | 1,918.723 | +6.5% |

All ranges overlap the latest historical endpoint below; these sequential,
buffered repeated-source observations do not isolate causal speedup or establish
cold-cache/device ceilings. No sample was discarded. The non-gating 1.6 MiB/s
small-file goal remains unmet: its backend median is 0.417 s and time outside
the backend is 2.941 s. The 4 GiB split is 1.579 s inside and 0.545 s outside
the backend. The rig excludes SQLite, workflow and GUI costs.

Receipts are under `build/executor-simplification-20260929/measurements/`,
prefix `result1-dadc1fef-20260929-153840-0bb41f93`: raw reports/logs, commands,
before/after manifests, environment, comparison and latest-comparison files.
The task's `scripts/five_band.ps1` and `five_band_receipt.py` adapt the existing
full-corpus driver to bind an exact precommit candidate; historical references
and all failed correctness receipts remain intact.

### Copied-file handle continuity — 2026-09-29

Measured the frozen precommit candidate on `a6e23064`, with exact dirty-source
hashes recorded, after 5,633 ordinary tests and the reviewed native lifecycle,
ACL and fallback-control migration. The same five F:→G: bands ran serially with
five samples each, normal rig metrics and readback. All 25 executions/readbacks
passed with recording OK and zero remaining reservations. Source identity and
the original 1,587-entry manifest stayed unchanged; product/rig/test/driver
dependencies stayed fixed, and manifest-owned cleanup removed all targets and
sidecars.

| Workload | Candidate median [min–max], s | MiB/s | Time versus source-consolidation result |
| --- | ---: | ---: | ---: |
| 1,000 × 4 KiB | 5.298 [4.705–5.661] | 0.737 | +57.8% |
| 512 × 128 KiB | 2.720 [2.045–2.855] | 23.530 | +53.2% |
| 64 × 4 MiB | 0.526 [0.396–0.589] | 486.584 | +50.6% |
| 4 × 128 MiB | 0.365 [0.345–0.424] | 1,401.369 | +15.4% |
| 1 × 4 GiB | 2.232 [1.963–2.312] | 1,834.736 | +4.6% |

These sequential endpoint measurements show slower medians, not a throughput
lift. The 4 KiB and 128 MiB ranges do not overlap the preceding run; the other
three do. The small-file goal remains unmet. Its backend median is 0.696 s and
time outside the backend is 4.616 s; the 4 GiB split is 1.820 s and 0.403 s.
Separate medians need not sum to the median total. These buffered repeated-source
results do not establish cold-cache/device ceilings or isolate the cause of the
change. No samples were discarded.

Receipts are under `build/executor-simplification-20260929/measurements/`, prefix
`result2-a6e23064-20260929-163929-812e188a`, including the immediate-predecessor
comparison against `result1-dadc1fef-20260929-153840-0bb41f93` and accepted
predecessor `a6e2306`. That comparison preserves the earlier precommit identity
instead of relabeling its recorded HEAD.

To discriminate handle-selection cost from the historical endpoint difference,
a bounded diagnostic ran four fresh processes in retained/fallback/fallback/
retained order on 1,000 × 4 KiB, five samples each. The fallback only overrides
`NativeFileSystem._copied_files` to return `None` inside that process; it uses
the current candidate's existing path-finishing branch, not the whole old
commit. Rig flags, readback and cleanup remain unchanged. All 20 samples passed
with matching dependency/source manifests and owned-target teardown.

The ten retained-handle samples have median 5.679 s [4.672–6.127], versus 5.909 s
[5.009–6.100] for fallback: −3.9% pooled time, with paired process differences
of −5.1% and −0.2%. Overlapping ranges and uncontrolled host variation prevent
a throughput-lift claim. The comparison does not support attributing the
historical +57.8% small-file delta to handle selection. It adds no gate and
discards no sample. Prefix `handle-abba-20260929-164758-75598d0c` retains the
four reports, mode/import receipts, driver hashes and summary. The preceding
`handle-abba-20260929-164651-840e44f6` failed before any sample or target creation
because the child lacked the repository import path; its exact driver and
failure receipts remain. The corrected child puts this checkout first before
product and rig imports; a supplemental read-only origin check records both
module paths against unchanged driver/source bytes.

### Planner-used drift facts — 2026-09-29

The frozen precommit candidate on `0d7dd6bf` passed 5,702 ordinary tests,
the unchanged oracle and differential before measurement. The same serial
five-band F:→G: procedure passed all 25 executions/readbacks with recording OK,
zero remaining reservations, unchanged 1,587-entry source and dependency
manifests, and complete manifest-owned target/sidecar cleanup.

| Workload | Candidate median [min–max], s | MiB/s | Time versus handle-continuity result |
| --- | ---: | ---: | ---: |
| 1,000 × 4 KiB | 6.489 [5.338–6.617] | 0.602 | +22.5% |
| 512 × 128 KiB | 3.503 [3.188–5.160] | 18.268 | +28.8% |
| 64 × 4 MiB | 0.708 [0.470–0.734] | 361.539 | +34.6% |
| 4 × 128 MiB | 0.354 [0.327–0.436] | 1,445.077 | −3.0% |
| 1 × 4 GiB | 2.482 [1.996–2.520] | 1,650.365 | +11.2% |

No throughput lift is established; four medians are slower and the small-file
goal remains unmet. Only the 128 KiB ranges do not overlap the preceding run.
The small-file backend/outside-backend medians are 0.776/5.720 s; the 4 GiB
split is 2.025/0.341 s. Separate medians need not sum to the total median.
These sequential, buffered repeated-source measurements do not isolate a code
cause or establish cold-cache/device ceilings. No samples were discarded.

Receipts under `build/executor-simplification-20260929/measurements/` use prefix
`result3a-0d7dd6bf-20260929-173343-1dcc369e`. The predecessor comparison retains
the raw `result2-a6e23064-20260929-163929-812e188a` identity and its accepted
commit `0d7dd6b`; candidate source hashes distinguish this later precommit tree.

### Equivalent verifier classifier cleanup — 2026-09-29

Measured the frozen precommit candidate on `84ce0fb2` after 5,702 ordinary
tests and 85 fresh package-consumer checks for the final README correction.
The verifier change removes a redundant Boolean classifier; it preserves the
component walk, filesystem queries and results. The same five serial F:→G:
bands passed all 25 executions/readbacks with recording OK and zero reservations.
Source/dependency manifests stayed fixed and all owned targets/sidecars were
removed by the existing teardown.

| Workload | Candidate median [min–max], s | MiB/s | Time versus planner-fidelity result |
| --- | ---: | ---: | ---: |
| 1,000 × 4 KiB | 6.218 [5.018–6.526] | 0.628 | −4.2% |
| 512 × 128 KiB | 3.452 [1.854–3.518] | 18.540 | −1.5% |
| 64 × 4 MiB | 0.489 [0.457–0.732] | 523.690 | −31.0% |
| 4 × 128 MiB | 0.329 [0.317–0.431] | 1,556.501 | −7.2% |
| 1 × 4 GiB | 2.320 [1.930–2.391] | 1,765.673 | −6.5% |

All ranges overlap the preceding run. These sequential endpoints establish
neither a causal throughput lift nor cold-cache/device ceilings; no sample was
discarded. Both performance goals remain unmet. Small-file backend/outside
medians are 0.764/5.463 s, and the 4 GiB split is 1.905/0.415 s. Separate medians
need not sum to the total median. The classifier cleanup saves no filesystem call.

The evidence prefix is `build/executor-simplification-20260929/measurements/`
`result3b-84ce0fb2-20260929-175649-85162057`. Its predecessor comparison preserves
the raw `result3a-0d7dd6bf-20260929-173343-1dcc369e` identity and accepted commit
`84ce0fb`; exact candidate hashes distinguish these two precommit trees.

### Full executor corpus after narrow runtime admission — 2026-09-29

Measured clean implementation `23589bd39a620ef4e5b31ddf8a9940a6628cadbf`
after its correctness gates and commit. This includes the prior unreadable-
descendant fix (`db03926`) and removes only adjacent target-root admission in
the concrete native runtime path. Broader error-classification work is deferred.

The original five F: source bands ran serially to fresh G: targets, five samples
per band in one fresh process per band. Preparation and initial preflight ran
once per band; normal pipeline metrics and native readback ran for every sample.
No method wrappers or profiler were installed. All 25 executions and readbacks
succeeded with recording OK and zero remaining payload reservations. The 1,587-
entry source stat manifest still matches the original assessment and is unchanged
before/after; all product/rig/driver hashes match across the run. All five targets
and rig sidecars were removed by manifest-owned cleanup. The five bands contain
1,581 payload files and exclude the original root marker, as both reference runs do.

This is the same Windows/CPython/xxhash and F:/G: NTFS storage profile described
below. Times cover executor calls only, excluding preparation, preflight,
readback and cleanup. Current and pre-optimization samples number five per band;
the separate full-corpus `db05e317` receipts contain three per band. Every sample
is retained, including the slower first 128 KiB and 4 MiB samples. No warmup or
outlier was discarded. The table reports median [minimum–maximum] seconds.

| F: → G: workload | Pre-optimization | `db05e317` | `23589bd` | Current MiB/s |
| --- | ---: | ---: | ---: | ---: |
| 1,000 × 4 KiB | 28.248 [27.367–29.745] | 7.992 [7.981–8.028] | 3.627 [3.538–4.204] | 1.077 |
| 512 × 128 KiB | 14.068 [13.983–16.096] | 4.255 [4.205–6.058] | 1.958 [1.881–3.925] | 32.678 |
| 64 × 4 MiB | 2.051 [2.019–2.107] | 0.641 [0.640–0.936] | 0.372 [0.354–0.659] | 687.661 |
| 4 × 128 MiB | 0.424 [0.414–0.449] | 0.311 [0.309–0.339] | 0.304 [0.295–0.325] | 1,683.043 |
| 1 × 4 GiB | 2.287 [2.104–2.385] | 1.956 [1.881–2.119] | 2.004 [1.779–2.120] | 2,043.484 |

Relative to `db05e317`, median execution time changes are −54.6%, −54.0%,
−41.9%, −2.1% and +2.5% in table order; against pre-optimization they are
−87.2%, −86.1%, −81.8%, −28.3% and −12.3%. The largest improvements remain in
per-file-heavy bands. The last two bands overlap the `db05e317` ranges, so these
observations do not establish a clear change there. Current 4 KiB backend time
is median 0.428 seconds, versus 3.199 seconds outside the backend. This aggregate
does not identify the remaining runtime cost. The earlier isolated 3.387-second
held-resolution reading is faster than this full-corpus 3.627-second reading;
neither comparison isolates the effect of this narrow runtime commit.

The `db05e317` table uses the separately retained full-corpus run, not the earlier
9.684-second per-checkpoint 4 KiB receipt. These are sequential historical
observations with different target spellings/plan fingerprints and sample counts,
not interleaved causal controls. Policy fingerprints, operation populations,
source identity and rig flags match. The endpoint delta includes cheap-cache,
stat-volume, held-resolution, ACL-refusal and runtime changes. Buffered repeated-
source results make no cold-cache/device-peak claim and exclude SQLite, workflow
and GUI costs. Stat identity cannot exclude historical same-stat content changes.

Evidence is under `build/root-admission-optimization-20260928/resume/` with prefix
`executor-runtime-full-23589bd3-20260929-000521-7fea29aa`: five `-fg-*.json/log`
pairs, `-before.json`, `-after.json`, `-comparison.json`, commands and environment
receipts. Retained drivers are `runtime_full_corpus.ps1` and
`runtime_full_corpus_receipt.py`. Reference raw reports remain in
`build/executor-bench-20260928-db05e317/` and
`build/executor-assessment-20260927/`. These are diagnostics, not release gates.

### Device ceilings — 2026-09-29

Standalone probes outside NamiSync, recorded to size the executor finishing and
direct-write work in [M1_PLAN](M1_PLAN.md). They are diagnostics, not acceptance.
Each used 4 MiB requests with one outstanding at a time, so they are not the
devices' queue-depth maxima. G: writes went to a uniquely named owned scratch
folder that was removed afterwards; F: was only read. Raw results and scripts are
in `build/executor-simplification-20260929/ceilings/`.

| 4 GiB probe | Median total, s | MiB/s |
| --- | ---: | ---: |
| G: buffered write, then file flush (the executor's current pattern) | 1.579 (flush 0.651) | 2,594 |
| G: unbuffered write, then file flush | 0.733 (flush ~0) | 5,588 |
| G: buffered write-through, mean of two | 1.883 | 2,175 |
| F: unbuffered read, mean of two | 0.835 | 4,908 |
| F: buffered sequential read, with or without `xxh3_128` | ~1.07 | ~3,830 |

The executor's 0.685 s large-file flush tail in the 2026-09-27 assessment is
therefore dirty cache draining through a buffered path that tops out near
2,600 MiB/s, not a slow device flush.

Per 4 KiB file on G: (median of three 500-file runs): create, write, close and
rename take 0.164 ms; adding a file flush gives 0.447 ms; adding a per-file
directory flush gives 0.677 ms; one directory flush per 500-file batch instead
gives 0.460 ms; write-through with per-file directory flushes gives 0.627 ms.
The current durability contract's raw floor is about 0.68 ms per file, against
about 3.5 ms per file in the executor at `23589bd`.

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
