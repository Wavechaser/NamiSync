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
report labels `driver_source` and `product_source` separately. Its bounded
native child and incomplete failures retain available child evidence and failure context.
An incomplete or v4-only observation does not satisfy current event-v5
transport correctness or the frozen SH-G-8 custody claim. Use the unchanged
custody tests and their authority below for that gate.

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
