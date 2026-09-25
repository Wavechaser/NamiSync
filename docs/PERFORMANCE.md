# Performance measurement methods and observations

This is the single owner for measurement fixtures, profiles, scaling axes,
sample aggregation, commands, artifact provenance and results. It records
historical observations at their measured revisions; it does not turn them
into a guarantee for the current checkout. [DEFENSE](DEFENSE.md#7-quantitative-evidence-and-measurement-authority)
owns evidence authority and consequence. [PRESENTATION](PRESENTATION.md#focused-scale-acceptance),
[BRIDGE](BRIDGE.md#evidence-and-ongoing-checks) and [INTERFACES](INTERFACES.md#sh-g-release-criteria)
retain behavior and gate decisions. AB-2 will change the named latency and
empirical representation-memory families to optional developer measurements;
until that atomic transition, the existing acceptance and validators remain.

## Reference profile and collection

The retained BR-G-42 profile is Windows 11 Pro build 26200, i7-13700K
(16 cores/24 logical processors), 63.7 GiB RAM, WD_BLACK SN850X 4 TB NVMe
for repository, fixtures and SQLite, CPython 3.13.14, SQLite 3.50.4, AC
power and no unrelated sustained workload. Warm p95 uses at least 30
samples; cold maxima use at least five fresh-process or cold-projection
samples. Record raw samples, source/runtime/profile, fixture seed, statistic,
child count, p95 and maximum. These identify reference evidence, not exact-
version launch admission. DEFENSE §7 governs changed-profile decisions.

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

## Plan, receipt and execution UI procedures

### Scoped selection witness

`test_plan_review_scale.py` constructs the 120,000-operation base fixture,
activates Copy, and times complete server membership resolution, workflow
deselection/decision derivation and Plan projection/summary refresh as one
diagnostic interval. It excludes fixture construction, WebView transport and
filesystem execution. A scope-matcher, workflow mutation or projection refresh
change reruns it. On 2026-09-17 the fixture matched 16,667 operations and the
interval was 1.207 seconds. This observation does not renew the Plan contract
at today's checkout.

### Scoped M1-8 receipt revalidation

Historical A8-03 permits a separately identified Tier-2 report for
`ui_get_plan_window_one_row_receipt` and `ui_start_execution_receipt`. Adapter
window enrichment and live-epoch setup before the execution receipt affect
these paths. Preserve the compact M1-7 contract, installed full-base fixture,
reference profile, untimed readiness/warmup, five fresh children per metric and
six samples per child. Each metric must meet nearest-rank p95 <=100 ms and
maximum <=250 ms; retain child identities and within/across-child dispersion.
All failed attempts and timeouts remain recorded. This scoped acceptance does
not renew the full 35-case collection or change its protected validator.

Use existing headed workload/child/readiness and authority-freezing primitives
through the A8-05 two-metric adapter/collector, with a separate scoped checker
reusing unchanged independent receipt/profile/byte checks. Freeze
the exact instrument/checker and additional product dependencies outside the
historical source manifest, including `workflows/execution_review.py`. Verify
physical source, wheel-member and installed bytes and Git-clean identities;
commit versioned raw provenance/receipts and a separate validation result.
Require controls for missing/reused samples, wrong identities and a maximum-only
failure. The historical finite method is retained here; the committed
[P2 authority](../tests/interfaces/web/m1_8_execution_receipt_authority.json),
[receipts](../tests/interfaces/web/m1_8_execution_receipt_receipts.json),
[result](../tests/interfaces/web/m1_8_execution_receipt_result.json), and
`tests/interfaces/web/_m1_8_execution_receipt_scale.py` retain exact artifact,
case and checker identities. Never filter
the full contract to make its terminal validator accept partial evidence.

Historical A8-05 versions this scoped report for the accepted rootless surface: the unchanged
base has 100,000 operations and 120,000 projection nodes, while its public window
has 119,999 rows. Initial settlement requires 256 current rows at revision/offset
zero and the independently derived `NamiSyncPriorV1` Previous paths first group.
Retain per-plan identities and the existing fresh-unused Plan population for the
start metric. Adapt only scoped fixture settlement/validation; preserve historical
producer, checker, contract and artifacts without fabricating a public root.

Before each launch durably publish the fixed ordered plan of two readiness
children (window, start), five window children and five start children, plus the
current launching state. Record accepted receipt/path/hash/process or the first
failure/timeout and bounded error/log evidence. Refuse restart/overwrite; stop on
first failure and obtain disposition before another collection. Independently
validate the final index embedded in raw evidence against exact receipt membership,
order, identities and hashes. Failed, launching or incomplete states cannot pass.
This preserves evidence custody in the trusted local collection model, not
protection against malicious rewriting. Both actual installed headed readiness
cases precede timed acceptance; headless fixture probes are only compatibility
evidence. Derive embedded authority OID from declared canonical bytes and bind
the named authority through filtered repository bytes to final HEAD and raw
receipts. Corruption controls cover these identities, rootless fixture premises,
attempt custody and budgets. Freeze the new adapter/checker/test dependencies
and verify postcommit source/evidence bindings; changed measured bytes invalidate
affected observations.

The P2 collection on 2026-09-20 completed its fixed 12 attempts with no failure.
The named `m1_8_execution_receipt_{authority,receipts,result}.json` artifacts
retain frozen provenance, exact attempt/sample membership and separate results.
Window receipt p95/max is 6.8/7.3 ms; execution-start receipt is 58.8/65.1 ms.
The full unmocked workspace validator passed before and after collection.
Ignored `build/m1-8-p2/run-01/` retains child receipts, launch index and logs.
These results apply to the P2 measured build; later UI edits reopen affected
cases under their own declared evidence. Final committed-source validation is
required in addition to receipt/result validation.

For historical P2 terminal reproduction, check out its recorded accepted
revision (`4bbf943`) with matching retained package bytes, then load the three
named artifacts and the unchanged compact contract, import
`tests/interfaces/web/_m1_8_execution_receipt_scale.py`, and invoke
`validate_authority_workspace` with the retained wheel/installed paths, then
`validate_receipts`, `validate_result` and `validate_committed_sources`.
`compact_authority` uses `plan_scale.canonical_json_bytes`; use its recorded
receipt OID and the raw artifact's authority OID. The exact retained invocation
is `build/m1-8-p2-terminal-validate.py --installed-root <site-packages>
--installed-wheel <wheel>`, executed with the project Python. It calls both
historical and supplemental checks unmocked and finishes with named-artifact
and clean-HEAD binding. The archived evidence records the retained installation.
The validator intentionally rejects later changed source bytes. Accepted U
evidence includes both P2 receipt metrics in its thirteen-case collection
and supersedes P2's measurements for the corresponding U build.
Do not rewrite frozen P2 artifacts or require their clean-HEAD check on U's tree.
Receipt/result checks use committed artifacts; workspace validation additionally
requires the matching retained wheel and installation. Missing package evidence
must not be described as a successful workspace reproduction.

Component windows, changed views, construction and projection-memory acceptance
retain their existing premises only while PlanReviewState, projection/order/
visible-sequence paths and measured retained graphs are unchanged. Live adapter
maps reference the existing membership mapping and stay outside those graphs.
Control receipt paths likewise require an unchanged timed dependency path.
Changing a premise reopens affected cases; later GUI changes rerun affected
receipts. The new execution overlay has structural population/work/byte bounds,
not a new numeric latency or memory claim.

### Scoped M1-8 execution UI revalidation

Gate U uses a separately versioned affected-path report rather than changing
the protected P2 or historical M1-7 authorities. Its fixed order is eight cold
interaction cases—update view, mutate selection, destructive start, confirm,
nondestructive start, pause, resume and cancel click feedback—followed by five
warm receipt cases: one-row window, start, pause, resume and cancel. Run all 13
untimed readiness children first, then five fresh children per case in that
order, for exactly 78 attempts. Each cold child contributes one sample and must
finish within 50 ms. Each warm child contributes six samples; nearest-rank p95
must be at most 100 ms and the maximum at most 250 ms.

Keep the compact contract's fixtures, equivalent untimed warmup, fresh unused-Plan
population and installed headed path. The scoped rootless adapter retains
120,000 projection nodes, 119,999 public rows and independently checks the
first Previous paths group. The approved U-v2 observation contract supersedes
pending-only feedback for the seven transient cold cases; historical M1-7/P2
contracts and observations remain unchanged.

At the first frame after an eligible connected control is clicked, require either
action-specific pending feedback or an exact successful typed outcome already
reflected in truthful action-correlated UI. Retain eventual exact settlement in
both cases. Empty pending, refusal, uncertainty, no dispatch or an unrelated state
never counts as success. Valid authoritative progress may advance beyond the
reply's immediate state: Pause initially returns pausing, Resume pending and
Cancel canceling. Do not force those intermediate states to linger. Destructive
Execute keeps its exact modal/snapshot endpoint; Confirm preserves its modal
safety requirements and proves the actual admission outcome separately.

Selection and control warmups prove an equivalent successful action, untimed.
Start observations bind the outgoing command to the expected plan request and
its transport-correlated reply to the current task/session. The reply carries
an execution run ID; the task summary retains its plan ID.
Warm control correctness retains accepted/code/before/after and identity facts
for independent validation, rather than treating session equality as acceptance.
The U adapter uses guarded replacements and one scoped JavaScript probe, with
exact source binding and byte identity outside the declared sites. The historical
producer remains untouched. Keep click-to-first-frame timing and all budgets;
no extra frame wait, post-frame repair or delayed product reply is permitted.
Failure details contain bounded scalar operands, never DOM graphs or unbounded
event histories. Failed observations remain failures, not acceptance samples.

Before launch, freeze and independently validate the exact source, CSS,
instrument, adapter, checker, control, wheel, installed-runtime and profile
bindings. Durably publish the complete attempt plan and current launch state;
stop at the first failure and refuse overwrite, restart or favorable retry.
Publish the existing immutable failure packet before updating the mutable index,
so a refused index replacement cannot suppress that packet. External monitoring
must not hold the index open while its writer replaces it on Windows.
Raw receipts and derived results have separate validators for exact identities,
order, samples, hashes and budgets. Positive and corruption controls must reach
the real supplemental byte and Git checks. Component construction, general
window/sort/selection and process-memory observations remain excluded only when
the final diff proves their measured code and retained graphs unchanged. Actual
collection occurs only after final source/control review.

The active U adapter is `tests/m1_8_execution_ui_benchmark.py`; its independent
checker and focused controls are `_m1_8_execution_ui_scale.py` and
`test_m1_8_execution_ui_scale.py` under `tests/interfaces/web/`;
`tests/assets/m1_8_execution_ui_probe.mjs` owns its shared observation mechanics
and is frozen as instrument source. Reuse unchanged
P2 rootless settlement and historical profile helpers; keep U metric membership,
cold/warm policy and attempt custody here. The three versioned artifacts are
`m1_8_execution_ui_{authority,receipts,result}.json` in that same test directory.
Acceptance requires the fixed collection and both source-binding
stages: full workspace/raw validation against the staged candidate before
commit, then clean-HEAD validation including the raw authority binding afterward.
Changes to measured product, instrument, checker, controls, package or native
profile reopen the affected evidence; unchanged product alone is insufficient.

The 2026-09-24 post-R2 recovery correction reran all 78 attempts with the fixed
profile and populations. Independent derivation gives a 20.3 ms worst cold
maximum, 72.0 ms worst warm p95 and 73.3 ms warm maximum, within the unchanged
limits. The three artifacts above retain evidence for the measured RC-1 source;
`build/m1-8-archive-20260924/evidence/recovery-close-20260924/delivery-01.json`
records staged and clean-HEAD
closure. Accepted predecessor run-03 remains under `build/r2-20260924/`;
historical failed runs remain separate and contribute no accepted samples.
R3 preserves that candidate's entire `build/` tree under the main checkout's
`build/m1-8-archive-20260924/evidence/`; the delivery register records integration
and the original-to-archive path mapping.


## Complete Plan collection and authority

The M1-7 plan projection, gesture and receipt budgets in PRESENTATION are independently
predeclared, profile-scoped **Tier 2** SLOs under DEFENSE §7. Crossing workflow,
bridge and browser layers within the plan slice is not a cross-slice operation
gate. This evidence closes no setup/execution/inventory/integrity aggregate or
release-resource criterion; it derives no ceiling from calibration. Preserve
the budgets and fixed reference profile rather than tuning thresholds to runs.

The compact representation uses the successor
`tests/interfaces/web/m1_7_plan_compact_contract.json`, with separately frozen
compact authority and measurement files. The legacy contract/authority/results
remain preserved under their original names and meaning. The successor records
the actual source projection, cached canonical/current orders, compact buffer
widths and populations, and reference sharing. Its memory case retains a complete
120,000-row base review while constructing a 240,000-row heavy review; both
realize canonical and filename-descending orders and current 256-row windows.
Baseline follows artifact construction but precedes review construction; sampling
continues through both reviews, sort/window work and final retained-state checks.
This includes the original projection-construction overlap and added order/visible
storage, without changing the existing metric ID, 320 MiB maximum or five cold
children. It makes no six-view or whole-headed-process memory claim. The current
producer cannot label this representation as legacy evidence; validators reject
mixed contract/authority/artifact families. Legacy compatibility is confined to
reading and checking preserved evidence. There is no legacy fixture generator,
product-data admission path or second runtime representation; retire the legacy
reader when its evidence is archived and no longer needs active validation.

Ordinary synthetic authority, receipt and corruption tests take fresh deep
copies of the frozen compact fixture expectations. Their expected answers do
not invoke the live generator. Separate live tests construct both actual fixture
families and compare population, raw-order witnesses and retained descriptors
against those frozen expectations; actual sibling sorting is checked against
the frozen order. These test expectations never supply measurement observations.

Before measurement, freeze the finite source/instrument/validator file identities,
actual native runtime/dependencies/profile, installed wheel and measured installed
file hashes, exact fixture family counts and expected raw-key order witnesses.
For the completed P9 candidate, the historical file population is supplemented
by a before/after source/installed/wheel-member binding for `core/execution.py`;
M1_PLAN records its digest and raw evidence. This covers the shared execution
structure without changing the fixed contract or claiming that review memory
measures a paused execution index. Final integration checks the supplemental
physical bytes and Git-clean HEAD identity as well as the named population.
The separately reviewed authority manifest admits those exact values; syntactic
hash validity or a self-reported profile is insufficient. The candidate may be
frozen by immutable file/blob hashes before its final atomic commit; no unverified
product commit is required. That final commit must contain the measured bytes.
Bind measured product files across source, wheel archive and installed files,
not merely three independent self-reported hashes. After the atomic commit,
verify clean measured paths and matching HEAD Git-clean blob identities against
the authority; retain physical measured-file hashes separately from checkout
line-ending normalization.

Use five fresh children for each cold case and five fresh children with six timed
warm samples each for every warm case (30 total). Record child identities, case
membership and per-child sample ordinals; report process count and within/across-
child dispersion with each statistic. P95 is nearest rank, index
`ceil(0.95 * n) - 1` in ascending samples. Every changed-view sample restores its
prescribed initial state outside timing; every timed Execute uses a fresh eligible
plan. A repeated no-op cannot stand in for a changed search/filter/collapse/sort.

Installed headed cases publish one plan by default, or two cold/seven warm plans
for fresh execution/control samples. These are valid completed/released tasks
published before startup. Settle each fresh view sequentially with exactly one
public open followed by one public 256-row window read. Retain proof of the
initial `opened` disposition, current revision zero, exact task/request/session/
path identities, total row count and first-row identity; the independent validator
checks this fixture receipt. Ordinary selection still waits for every exact source
view outside timing. This prepares a current review for interaction measurements,
not concurrent cold-start latency; separate cold-construction cases remain timed.
Freeze their distinct task/request/plan-session/path identities
and prove each execution sample unused before admission. No private task/view
rewrite or synthetic startup event prepares a sample. Related idle views are
part of this finite fixture; the separate component memory case does not certify
their aggregate headed-process memory.

The fixed Plan case set contains 35 cases. Destructive Execute-to-modal,
Confirm-to-pending-frame and non-destructive Execute-to-pending-frame feedback
are separate 50 ms maximum cases. The non-destructive fixture deselects risk-bearing
operations through the authoritative service outside timing. The typed Execute
receipt starts at Confirm submission and ends at the actual TaskStartView,
including selection commitment and admission but excluding human decision time
and admitted execution work. It retains the 100 ms p95 / 250 ms maximum budget;
an outer asynchronous transport token is not that endpoint.
The passive headed receipt observer registers on the production document-message
channel before submission and removes its listener on settlement or timeout;
executable controls verify delivery alongside other listeners and reject missing
registration. Execution/control cases share this observer.

The contract identifies each fixture variant, untimed setup, timed transition,
endpoint and correctness assertion. Evaluate search, filter, collapse, all allowed
sort directions, reset and subsequent unchanged windows separately; do not pool
fast cases. Reset begins in a non-path sort and may cover explicit path-ascending
sorting only when deterministic tests prove the same measured mechanism. Include
balanced/widest siblings, ties/unavailable keys, raw numeric/Unicode cases, depth
32 and construction/staging overlap in the existing fixtures. The synthetic root
counts within the 20,000 structural allowance, not in addition to it.

Before the expensive sample set, run a separate untimed readiness pass against
the current frozen inputs. It covers all 35 contract IDs in 15 children: one
shared component child for the 21 non-memory cases, one isolated memory/staging
construction, and the 13 existing headed cases in fresh children. Selection runs
first and a failure stops the pass. Each case uses its existing setup and
correctness path with one transition; cold construction and memory have no
warmup. Full fixture populations remain intact. Readiness carries no timing or
retained-byte samples, does not replace quantitative acceptance, and cannot warm
or provide task state to the fresh measurement processes.
The parent process allows 600 seconds for the shared 21-case component readiness
group and 300 seconds for every other readiness child and each measurement child.
These are process liveness safeguards, separate from the fixed measurement
budgets; timeout leaves the collection incomplete and supplies no acceptance.

Selection setup identifies an enabled, checked operation row through the public
view and its connected checkbox. Warmup must publish pending and settle to an
advanced authoritative selection revision with that same row unchecked; the
measured action requeries that row. Public summary/window reads are untimed
witnesses, not asynchronous completion events for the synchronous mutation path.
The historical M1-7 pending-frame criterion is unchanged; failure after verified
eligibility is a stop for review, not permission to delay product receipts or
weaken that test. Scoped U uses the separately approved observation contract above.

Retain each checked child receipt atomically under a unique ignored run evidence
directory. A separate atomic index binds its frozen authority, case, planned
ordinal, launch/process identities, path and hash. Record attempts before launch;
failures and interruptions leave the collection incomplete and preserve receipts
already produced. This does not change measurement child or terminal schemas.
Partial evidence cannot satisfy the terminal validator and is not automatically
resumed, merged or reused. Any future reuse requires explicit validity review;
changing measured instrument bytes invalidates cross-revision reuse.

One verdict-free terminal artifact records genuine observations and provenance;
the independent validator checks exact case/count membership, source/profile and
fixture authority, P95 and maximum budgets. Validator corruption controls must
reach wrong-but-well-formed identities, wrong populations, missing/extra cases,
reused child identities and maximum-only failures. Local click feedback and typed
receipts use the installed headed production path; projection-only measurements
do not establish either. Deterministic structure/permutation and bounded-work
witnesses remain separate from elapsed time. Rerun after changes to any measured
source, key, comparator, index, publication, retention or admitted profile.

Common receipt checks belong to validator-local helpers, independent of producer
checks and constants. Collection callers retain path, byte hash, planned order
and partial-prefix validation; readiness retains complete coverage; terminal
acceptance retains complete membership and aggregate budgets. Each entry keeps
its own identity-reuse checks. Inspecting valid partial evidence never grants
terminal acceptance. Baseline/candidate public-entry corruption comparisons
protect these boundaries when consolidating their implementation.

The former R7 consolidation batch delivered R7-1–R7-4 before suspension; its
R7-G full acceptance was not completed. Its checkpoint-specific Tier 1/Q-local
and final-run procedure is historical in the
[retired register](obsolete/M1_7_ABLATION_STUDY.md). It is not a standing
instruction to resume or requalify that abandoned batch. Historical evidence
remains immutable. The current performance contracts and acceptance policy
above are unchanged; [POST_M1_8_ABLATION E1](POST_M1_8_ABLATION.md#7-measurement-and-evidence)
proposes optional benchmark treatment but does not enact it. Newly activated
work uses its named verification under the then-operative policy.

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

Use a fixture with 50 runs and 1,000,000 items,
including one 100,000-item run, and record:

- Windows build, CPU, storage, Python and SQLite versions;
- cold versus warm cache state;
- transaction count and window count;
- p50, p95, and maximum window-commit latency;
- peak pending event count and serialized bytes;
- 50-run summary latency and 256-row item/event page latency.

The 2026-08-05 baseline ran
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
irreplaceable evidence. No raw file is moved or deleted by AB-1.
