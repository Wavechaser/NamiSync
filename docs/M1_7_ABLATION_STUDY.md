# M1-7 ablation study

Study date: 2026-09-16. Target: the inclusive seven-commit series `ae3daf6`
through `5986c57`, compared with `40ca76f`. This is a completed discovery report,
not an implementation register or a change to accepted product/evidence policy.
M1_PLAN owns study closure and any subsequent implementation scope.

The best next reductions are duplicated control flow and test machinery, not
removing the layers that independently establish reviewed execution safety.
There are useful small product cleanups, several substantial harness
consolidations, and one larger representation proposal worth a separate design
decision. Reversing the delivered compact-storage, selection-digest or shared
execution-structure optimizations would be poorly justified.

## Scope and evidence strength

The method was coarse to fine: inclusive diff census; Python AST/function
inventory; ownership and contract reads; selected function/caller tracing;
two bounded Codex sidecar reviews; an independent single-session Claude review;
then counterexample checks and synthesis. We did not individually review all
22,273 added lines or claim exhaustive defect coverage.

| Population | Changed files | Added lines | Removed lines |
| --- | ---: | ---: | ---: |
| Product | 20 | 5,322 | 442 |
| Tests, helpers and evidence | 46 | 16,097 | 272 |
| Documentation | 11 | 854 | 91 |
| Total | 77 | 22,273 | 805 |

Tests account for 72.3% of added lines. Three new files alone—the 3,998-line
benchmark producer, 1,996-line independent validator, and 1,837-line scale test
module—account for 7,831 lines, 48.6% of test additions. These are Git textual
counts, not executable LOC, maintenance estimates or a proposed deletion quota;
the large single-line JSON evidence files illustrate the distinction.

Most framework breadth originates in `ae3daf6`; the later commits introduce
targeted representations and reuse to meet the fixed scale criteria. Therefore
this study evaluates the integrated result rather than treating the last
performance commits as disposable patches.

The coarse ownership map explains which apparently similar code can be merged:

| Owner | Responsibility that must survive |
| --- | --- |
| Workflows | Immutable Plan structure, dependency-closed selection, risk and raw sort facts |
| Service / TaskLifecycle | Reviewed selection admission / application claims, receipts and compensation |
| TaskRegistry / PlanReviewState | Delivery generations, replay and release / process-local review and view revisions |
| Browser renderer / app / bridge | View geometry and input / asynchronous intent / transport and exact retry |
| Benchmark producer / independent validator | Genuine observations and retained provenance / independent membership, identity and budget verdict |

Recommendations below use three evidence levels: **observed duplication**,
**bounded experimental support**, and **design proposal**. The canonical
comparator and a selected synthetic-fixture cohort were ablated in isolated copies. No larger
consolidation has been implemented or benchmarked, and no saving in time,
memory, test count or LOC is promised.

## Ranked candidates

| ID | Candidate | Judgment | Benefit / risk |
| --- | --- | --- | --- |
| A1 | Reuse receipt validation inside the independent validator | Recommend | High maintenance benefit; moderate evidence risk |
| A2 | Reuse producer receipt persistence and attempt bookkeeping | Recommend | High clarity benefit; moderate interruption risk |
| A3 | Separate synthetic corruption fixtures from live scale construction | Recommend; experimentally supported for five controls | Strong test isolation; low/moderate risk |
| A4 | One browser admission-retry algorithm | Recommend | Removes duplicated state machine; moderate replay risk |
| A5 | One service selection-admission core | Recommend narrowly | Removes duplicated policy transitions; moderate/high race risk |
| A12 | Derive immutable safety facts once per successful selection mutation | Recommend narrowly; Claude finding independently traced | Removes repeated workflow derivation; preserve validation and ownership |
| A6 | Remove test scenario coupling and source-count prescriptions | Recommend in separate small outcomes | Strong refactor freedom; retain same-level fault detectors |
| A7 | Stop constructing a full per-operation preview for internal desktop updates | Design proposal | Removes an unnecessary transfer representation; public compatibility matters |
| A8 | Separate immutable Plan topology from selection overlay | Investigate only if allocation remains a material hotspot | Largest product simplification potential; broad representation/evidence impact |
| A9 | Retire unused in-place projection replacement and obsolete comparator branches | Recommend as separate cleanups | Small, concrete complexity reduction; comparator experimentally supported |
| A10 | Retire active legacy measurement interpretation | Conditional archival decision | Removes a second evidence family; historical reproducibility must survive |
| A11 | Reduce Plan-again instrumentation and its mirrored oracle | Small oracle reduction now; tracer retirement conditional | Less source-spelling coupling; potential diagnostic loss |

These are candidates, not twelve authorized implementation checkpoints. In
particular, A6 and A9 each contain independently committable small outcomes.

### A1 — Consolidate within the validator, preserve oracle independence

`tests/interfaces/web/_plan_review_scale.py:520` validates measurement receipt
shape, case, runtime, sample population, correctness and numeric fields while
inspecting a collection. Its terminal path repeats these checks at `1674` and
`1723`. Readiness receipt checking similarly overlaps at `362` and `564`.

Extract validator-local measurement/readiness receipt checks used by
`validate_collection_index`, `validate_readiness` and `_validate_children`.
Keep path/hash checks and collection ordering at the collection boundary;
keep uniqueness checks at every existing collection/readiness/terminal boundary.
Only complete membership and aggregate budgets require terminal evidence.
An incomplete valid collection must remain inspectable without passing the gate.

This removes multiple implementations of the same receipt invariant. It does
**not** unify producer checks with validator checks, nor make the validator
trust producer-generated expected answers.

**Falsifying gate:** apply the same malformed-common-field corpus through partial
and terminal entry points; both reject it. An incomplete well-formed collection
remains inspectable and fails terminal acceptance. Preserve child identity reuse,
wrong-but-well-formed identities, maximum-only failures and P95 failures.

### A2 — Consolidate evidence publication, not readiness and measurement

`tests/plan_review_benchmark.py:3409` and `3592` repeat the receipt lifecycle:
check a child result, publish canonical bytes, remove staging output, hash the
published receipt, append wrapper/index entries, advance the next attempt, and
retain an incomplete collection on failure. They already share index publication.

Make receipt persistence and accepted-attempt bookkeeping one small producer-local
operation. Keep `run_readiness` and `run_gate` explicit: their plans, watchdogs,
receipt schemas, fresh-process requirements and terminal artifacts differ.
There is no reason to build a reusable benchmark framework for this extraction.

**Falsifying gate:** preserve interruption controls in
`test_plan_review_scale.py:923`, `983`, `1085`; inject failure immediately around
receipt publication and index advancement. Earlier accepted receipts survive,
and the next/failed index identifies the first unaccepted attempt. Selection-first
readiness, process freshness and no automatic partial-result reuse remain.

### A3 — Make validator controls independent of expensive fixture realization

`test_plan_review_scale.py:430` caches live manifests for both fixture families.
The synthetic `_authority_inputs` at `438` feeds them into authority controls
at `533`, despite supplying fabricated source/runtime bytes elsewhere. Through
`plan_review_benchmark.py:288` and `3277`, creating the manifests also creates
real full-population projections and a review state.

Use deep copies of frozen compact fixture expectations for synthetic corruption
controls. Retain separate live generator checks at
`test_plan_review_scale.py:1175` and `1233`, comparing observed populations,
ordering and retained representation to the frozen expectations. Actual
acceptance runs must still observe their actual fixtures.

**Falsifying gate:** synthetic corruption tests pass with live fixture generation
stubbed to raise; dedicated generator tests fail on a deliberate population or
order drift. Existing caching already avoids repeated construction within a
process, so repeated per-test savings must not be claimed.

**Experiment E2:** five existing controls (valid terminal artifact, incomplete
retained representation, missing/extra cases, maximum-only failure, fixed
statistic failure) passed unchanged, then all five passed with frozen manifests
and live generation forced to raise. Deliberately deleting only the validator's
maximum-budget rejection caused the maximum-only control to fail with
`DID NOT RAISE ValueError`. The observed single-process runs were 17.48 s and
0.28 s; these are diagnostic timings of this selected cohort, not a repeatable
speedup estimate or release criterion. No dedicated live-generator test was
removed or claimed covered by the synthetic cohort. The exact patch/logs survive;
the disposable copy was removed.
The experiment patch is cohort-only and unsuitable for direct integration:
the replaced helper is also used by live tests outside that selected cohort.
Implementation must split the synthetic and live manifest providers, then prove
the live tests still detect deliberately changed fixture populations/orders.

### A4 — Give admission replay one implementation

`namisync/interfaces/web/assets/bridge.js:677` (`submitStart`) and `798`
(`startExecution`) each own an `automaticReplayUsed` flag, uncertainty
classification, one automatic replay and an exact manual-retry closure.

Extract one private recovery helper receiving the frozen payload, command,
validator and timeout. Keep command-specific payload construction and result
identity checks, including Plan-again returning a new task and same-task Execute.
Read retries at `704`, `740`, `760` can separately share their much simpler
transport-error retry operation; do not give reads mutation semantics.

**Falsifying gate:** exercise production `startExecution`, not only the mocked
wrapper in `tests/assets/task_shell_probe.mjs:140`. Check lost first/second reply,
non-uncertain errors, repeated manual retry, same logical command/payload, fresh
transport identities and no extra automatic replay after the first allowance.
Retain the real bridge identity cases in `bridge_interactive_probe.mjs:268`.

### A5 — Share selection admission, retain distinct task and general wrappers

`namisync/interfaces/service.py:1046` and `1264` separately implement
reviewing/committing/committed checks, revision validation, nonempty selection,
destructive confirmation, `commit_plan`, session submission and final
commit-versus-rollback bookkeeping.

The smallest useful consolidation is a private selection-reservation/commit
operation and matching completion logic. Keep task follow-up claims, delivery
factory, compensation and response shape in the task wrapper. Keep the general
API's optional expected revision for pristine CLI selection and caller-supplied
verification choice in its wrapper. Do not replace these differences with a
general callback-heavy admission framework.

Replay must stay before fresh selection inspection. The lock-protected
check/reservation remains atomic, external work stays outside that lock, and
finalization remains conditional on the identical retained state. The delivery
factory changes generation and saves prior delivery; it is not a pure callback
constructor that can be freely reordered.

**Falsifying gate:** retain `tests/test_bridge_service.py` admission-failure
rollback (`805`, `822`), follow-up-claim release (`886`), command single-flight
(`1151`), pristine omitted revision (`1790`) and effective destructive scope
(`1850`), plus TaskLifecycle/TaskRegistry closing and recovery races. Verify
post-admission preflight refusal remains committed, and a lost response recovers
the admitted receipt rather than reissuing effects. This is a concurrency-sensitive
refactor, not a low-risk deduplication of text.

### A6 — Remove tests' accidental coupling before building shared harnesses

Three narrowly supported opportunities:

- `tests/assets/task_shell_probe.mjs:607` truncates `planWindows`, and `615`
  pops another entry solely to keep later global receipt ordinals stable.
  Capture named scenario-local deferred receipts. Add an earlier unrelated
  window request as a variation: later scenarios should need no renumbering.
- `tests/assets/plan_review_probe.mjs:165` creates a historical consent checkbox
  outside the production panel, then `327` asserts it is still checked. Remove
  that disconnected demonstration. Keep the production no-persistent-checkbox
  assertion and request/revision snapshot tests (`task_shell_probe.mjs:695`, `757`).
- `_task_shell_headed_child.py:1373`, `1478`, `1597` repeat Execute focus,
  geometry, hit testing and polling; exit-barrier setup repeats at `1435`, `1633`.
  Small local driver helpers can serve explicit cancel, pointer and keyboard
  scenarios. `test_task_shell_headed.py:75` currently mandates exact occurrence
  counts of those copied mechanisms. Replace those prescriptions with ordinary
  executable helper refusal checks, keeping installed native input witnesses.

**Falsifying gate:** named deferred-receipt probes still detect stale windows and
latest-review-instead-of-captured-intent faults. Driver checks still reject a bad
hit target and failed stage/barrier; real headed tests retain Escape, Tab
containment, Cancel focus, pointer/wheel blocking, closing protection and focus
restoration. Native tests alone are not a substitute for retiring an ordinary
detector without replacement. Earlier TEST_REFINEMENT ST-5 used this same
same-level-detector condition.

Do not start with a universal fake DOM or delete one of renderer/app/bridge/native
test layers merely because they assert related behavior. They reach different
failure boundaries.

### A7 — Narrow the internal selection transfer

`service.py:2295` materializes all selected IDs and one
`SelectionOperationView` per operation. `get_plan_projection` (`1169`) creates
this preview although projection construction already has the exact immutable
`ExecutionSelection`. After mutation, `web/drain.py:899` separately requests
membership and reconstructs an exclusion mapping from all preview operations.

An internal immutable revision-bound snapshot could carry the existing decision,
revision/state and summary facts directly; generate the full public
`SelectionPreviewView` only for its actual API consumers. This removes a transfer
representation and the split preview/membership choreography without changing
workflow ownership of selection. The snapshot must remain an internal typed
port value; never serialize the workflow graph into the browser.
Use the same mutation owner and select its output representation; do not create
a second desktop-specific selection mutation algorithm.

**Falsifying gate:** unchanged public CLI/API preview output, exact revision and
artifact rejection, frozen membership identity, dependency exclusions and risk
facts. Check direct consumers in `interfaces/cli.py`, `task_port.py`, command view
serialization and `_public_view_witnesses.py`. Preserve no cached full preview
tuple/operation graph. Quantitative claims require fresh selection/interaction
measurements; static elimination of allocation is not a measured latency result.

### A8 — Consider a real selection overlay instead of cloning immutable rows

`workflows/plan_projection.py:530` calls `dataclasses.replace` for every row on
selection change, including structural and notice rows. The new `PlanProjection`
copies its indexes. `web/plan_review.py:309` then rebinds canonical/current
orders, and `visible_sequence.py:205` rebinds nodes and copies the ID lookup.
This is an overlay in behavior, but its representation remains a new row graph.

Separate stable topology/display/raw-sort facts from a selection overlay containing
membership, counts and exclusions. Orders/visibility refer to stable topology;
bounded row serialization combines it with the current immutable overlay. This
could eliminate row cloning and the trusted rebinding paths. Derive the overlay
in workflows; the adapter must not invent selection policy.

This is a **design proposal**, not a proven net simplification. It adds an explicit
join at row access and touches public projection consumers. Do not simultaneously
introduce incremental rollups, new caches, per-node wrappers or a new tree library.
Full O(N) rollup may remain the simplest algorithm.

Order rebinding already shares compact arrays; current code does not re-sort or
rebuild visibility on selection. The opportunity is node/map allocation, not
removing work that is already avoided. Also, `drain.py:889` consumes
`node.selection` directly: joining only at window serialization would leave that
consumer stale. Without evidence that allocation is material, first consider
the smaller removal of redundant immutable-map copies.

**Falsifying gate:** retained filters/search/collapse/order survive selection;
dependency-induced exclusions, prior-path and notice rows remain correct; view
and selection revisions publish atomically; old snapshots do not change; no
old row graph survives through cached orders. Update the representation-specific
test at `test_plan_review.py:438` to verify the retained guarantee rather than
requiring exactly one projection clone. Run workflow/interface consumers,
ordinary/import gates and affected fixed scale/memory criteria before acceptance.

### A9 — Remove unused mechanisms before introducing replacements

**Unused replacement route.** `web/plan_review.py:234` has a 44-line
`replace_projection` method. Repository search finds four call sites, all in
`test_plan_review.py` (`127`, `270`, `477`, `498`). Production
`TaskRegistry.open_plan_view` (`drain.py:753`) constructs a new state; staging
memory evidence also constructs another state. Removing the in-place method
would remove a second publication path and its dedicated invalidation tests.
Keep validation when acquiring a new state, selection-only updates, failed
publication retaining the prior usable view, and new-view identity. Active
ARCHITECTURE/PRESENTATION language currently documents full replacement; align
that language with state replacement in the same cleanup. Future inventory
design is not a reason to retain an unused Plan-specific mutation API.

Do not delete all four calling tests wholesale: preserve the view-gesture
retention case through `replace_selection`, the constructor half of malformed
acquisition tests and exhaustion coverage for surviving revision changes.
PRESENTATION's broader conditional rebuild guarantee—retained sort and atomic
publication—still applies wherever rebuilds remain supported. Fresh acquisition
alone does not prove that guarantee, even though no current caller needs this
particular in-place method.

**Obsolete comparator branches.** `workflows/plan_projection.py:400` is the sole
caller of `_compare_nodes` (`917`), always with PATH/ASCENDING. Real sorts use
the stable raw-key algorithm at `414`. Replace the comparator adapter with
`(rel_path_key, node_id)` and remove its unreachable filename/size/mtime branches
and unused comparator import/helper. Keep all real-sort behavior.

**Experiment E1:** an isolated faithful source copy ran both
`tests/test_plan_projection.py` and `tests/interfaces/web/test_plan_review.py`:
33 passed in control and 33 after the comparator ablation. A deliberately reversed
canonical key order caused the existing nonlexical-order test to fail on
`(0, 1, 2) != (0, 2, 1)`. This demonstrates that the retained neighborhood accepts
the simplification and detects that specific causal fault. It is not full-suite,
headed, performance or general-equivalence evidence. The disposable copy was
removed after saving the exact patch and logs; production/tests remain unchanged.

### A10 — Archive legacy interpretation instead of carrying it forever

`_plan_review_scale.py:1248` branches into legacy retained-representation
validation (`1328`). `test_plan_review_scale.py:1264` actively revalidates the
historical failed artifact and expects a budget rejection. This is **not dead
code**: PRESENTATION explicitly retains it until historical evidence is archived
and no longer needs active validation.

If historical reproduction can use a pinned validator revision, preserve original
contracts/authority/results and that validator, then let the current validator
support only the compact family. Keep explicit obsolete/mixed-family rejection.
Do not delete failed history, reinterpret it as accepted, or change budgets.

**Falsifying gate:** archived bytes and their known failed verdict reproduce under
the pinned historical validator; current compact evidence still validates and
legacy/mixed inputs refuse. This requires an archival disposition, not an
unannounced cleanup of a supposedly redundant branch.

### A11 — Simplify the tracer oracle; decide separately whether to retain tracing

`tests/interfaces/web/_plan_again_trace.py:317` supplies 18 source replacement
anchors across three assets, transformed at `344`. The test at
`test_setup_headed.py:305` repeats nearly the same regex/newline/replacement
algorithm using that same replacement table. That is weak independence.

Replace this mirrored output calculation with explicit anchor/hash checks,
normal/exception restoration, no-partial-write behavior and bounded sanitized
trace/delegate-once tests. Retain concrete expectations independent of the
transformer where semantic transparency is claimed.

The larger deletion—retiring source-rewriting instrumentation—is conditional on
its diagnostic purpose being discharged. All four parent/child consumers matter:
Setup and task-shell parent tests plus `_setup_headed_child.py` and
`_task_shell_headed_child.py`. The trace validator at `502` checks vocabulary and
shape, not a complete causal success sequence.

**Falsifying gate:** small cleanup preserves restoration and failure controls.
Tracer retirement retains uninstrumented installed Plan-again flows, fresh
identities, changed source/target visibility, exact retry and 48-task capacity.
Explicitly record the lost per-boundary diagnostic trace; do not pretend it has
no value merely because it is optional.

### A12 — Reuse safety facts within a selection mutation

Claude identified this candidate; direct tracing confirms it for the successful,
non-replayed branch of `service.py:965`. Both `_resolve_plan_selection_ids`
calls (`967`, `972`) unconditionally derive a pristine selection, even when
their identifier tuple is empty. `apply_selection_mutation` at
`workflows/selection.py:220` derives safety exclusions again; the final decision
at `service.py:983` derives them a fourth time through `selection.py:133`.
The resolver additionally computes full selection digest/risk/byte facts merely
to obtain toggleable membership. This repeated calculation is unnecessary.

Start with no-work resolution for empty identifier tuples and avoid deriving
folder toggleability for direct operation IDs when the authoritative workflow
mutation will validate them. For the remaining shared calculation, let a narrow
workflow operation own call-local safety facts/indexes, mutation and the resulting
decision. Keep user deselection/dependency closure distinct from baseline safety
closure. Preserve public selection functions and their malformed-input rejection;
do not let an external caller supply an unchecked exclusion dictionary that
bypasses the safety decision. Avoid a retained cache or a generic context framework.

**Falsifying gate:** blocked correspondence, incomplete scans, unknown IDs,
direct operations, folder gestures, deep dependencies, reselection, noops/replay
and stale revisions produce identical memberships, exclusion reasons and digests.
A counted witness should establish that redundant derivation is gone on the
chosen service path; it does not replace those behavioral checks. Refactor only
the selection path, with service/workflow and browser consumer coverage.

No latency gain is measured. In particular, the benchmark's
`depth_32_selection_preview` (`plan_review_benchmark.py:405`) directly calls
`derive_execution_selection`; it does not exercise the full four-derivation
service gesture. Select quantitative reruns by their actual measured path.

## Boundaries to retain and lower-priority proposals

- Keep workflow meaning, service composition, lifecycle effect custody and
  registry delivery distinct. Similar task/session identities protect different
  owners. Merge duplicated local algorithms, not these ownership boundaries.
- Keep immutable selection/digest reuse and shared execution structure with
  mutable overlay detachment. They removed repeated work needed for accepted
  scale; public construction checks and fresh execution preflight remain distinct.
- Keep compact source positions, inverse ranks and visibility metadata. An
  ordinary object-list rewrite would need to re-establish the fixed budgets.
- Keep producer/validator expected-order and statistical independence, physical
  source/wheel/install identity versus Git-normalized identity, maximum as well
  as P95, and readiness separate from quantitative samples.
- Do not simply delete `_validate_structure` because the workflow validates
  topology: the adapter also checks text and unique node identities. Shared
  structural authority is a possible later design, not evidence that every
  existing check is redundant.
- App `changePlanView` (`app.js:818`) and `changePlanSelection` (`932`) repeat
  summary/anchor/window settlement. A narrow extraction is plausible, but their
  conflict checks, fallback offsets and uncertainty recovery differ. Rank it
  below A4/A5; characterize those differences before changing them. Renderer
  viewport coverage and app in-flight coalescing remain separate responsibilities.

## Recommended sequence and closure cost

Start with the small A9 cleanups and A6 harness coupling removals. Next consolidate
A1/A2 and decouple A3, each with independent fault controls. A4/A5 then reduce
duplicated state transitions, and A12 removes repeated selection derivation.
Evaluate A7 before deciding whether A8's larger
representation redesign earns its complexity, and require hotspot evidence for
A8. A10/A11's retirements require
explicit evidence/diagnostic dispositions, not automatic inclusion.

The benchmark producer, validator and its test module are themselves named source
inputs in the compact contract. Test-only edits there are not provenance-free.
Any implementation must classify whether it changes an instrument, validator,
fixture or only test support and refresh the required authority/evidence; old
measurements cannot silently certify changed measured bytes. Preserve historical
P9 evidence. No threshold weakening or 175-child rerun was performed in this study.

Before implementation, expand each accepted outcome in M1_PLAN with finite
production/test/doc populations, exact atomic boundary and regression gate.
Use existing department/consumer and ordinary/headed requirements. Do not bundle
all candidates into another M1-7-sized checkpoint.

## Independent review disposition and verification

The requested reviewer used `claude-opus-5`, `xhigh`, session
`bfd6b79e-d74d-4714-a0cc-38bdafe5b5e2`, with only Read/Grep/Glob. Its first response
reports zero spawned subagents and no permission denials. The targeted challenge
continued the same session and settings; no second Claude review thread was
created. Two Codex sidecars separately reviewed measurement and browser/harness
families, followed by bounded adversarial checks. Their suggestions were traced
against source before inclusion.

| Claude suggestion / claim | Validated disposition |
| --- | --- |
| A1: retire tracer | Narrowed to A11; four consumers, including the Setup child, and diagnostic loss must be accounted for. |
| A2: union fake DOM is always stricter | Rejected as stated. Added fake behavior can mask failures; shared fidelity requires explicit tests, not a union-by-assumption. Scenario coupling is the better first target. |
| A3: remove source-literal harness assertions | Accepted narrowly in A6, preserving same-level executable fault detection and real native input. |
| B1: collapse destructive-fact fields | Incorporated into A7's internal owned snapshot direction; keep emitted/public compatibility and real ingress checks. |
| B2: four safety derivations per gesture | Independently confirmed for the successful fresh mutation branch; added A12 with workflow ownership and call-local reuse. |
| B3: O(N) membership round trip | Cost claim rejected: valid cached membership access is identity checks plus an existing frozenset. A7 still removes split transfer choreography; it must define freshness, not silently drop the recheck. |
| B4: add a new order-owner abstraction | Prefer A9's unused-path removal first. A narrow documented facade for trusted sorting may help, but no new PlanOrderSet or polymorphic ordering framework is justified. |
| B5: dormant constructor can become optional audit without changing contract | No direct VisibleSequence constructor caller was found, but the equivalence claim is rejected. Test-only auditing does not preserve reject-on-construction; public API retirement requires a separate explicit disposition. Keep PlanProjectionOrder public validation. |
| B6: replace public preview operations with exclusions | Narrowed to A7's internal transfer; public DTO/witness/serializer consumers prevent treating the field change as transparent. No claimed halving of cost. |
| B7: shared retry helpers | Accepted in A4. Small ingress predicate cleanup is secondary and must preserve complete-request bounds. |
| C1: retire legacy family | Accepted conditionally in A10; historical reproducibility and current-schema refusal stay. |
| Selection transformation preserves index maps by reference | Corrected: PlanProjection construction copies both maps; visibility rebinding copies the ID map. Order rebinding does share compact arrays. |
| Census and automatic rerun-cost ranking | Corrected to the Git census above. Evidence dependency matters; neither blanket zero-cost claims outside a file list nor one full rerun per commit is justified. Preserve coherent scopes rather than accumulate every candidate into one giant checkpoint. |

Claude's same-session follow-up accepted all six groups of corrections and
withdrew the erroneous census, O(N) membership claim, public-field narrowing and
constructor-audit equivalence. It narrowed safety reuse to a workflow-internal
operation and corrected the benchmark attribution. This report adopts those
corrections, not every subsequent suggestion: missing direct constructor calls
do not establish that its invariants lack all other test coverage, and selection
reuse does not automatically justify a new sorting abstraction.

Raw Claude material is retained as review evidence, including challenged claims;
it is not the final recommendation authority. Both invocations completed
successfully in the same session with zero Claude subagents. The CLI's per-model
usage across the two invocations is:

| Model | Input | Cache creation | Cache read | Output | Thinking (included in output) | Reported USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| claude-opus-5 | 144 | 258,059 | 10,300,088 | 70,007 | 36,795 | 9.481529 |
| claude-haiku-4-5-20251001 (CLI-reported auxiliary usage) | 1,408 | 0 | 0 | 20 | 0 | 0.001508 |

Total reported cost: **$9.483037**. The configured review and all observed
assistant tool messages used Opus 5; the CLI separately reported the small
auxiliary Haiku usage above. It was not another review thread or spawned agent.
Cache-read tokens are repeated context usage, not unique source lines inspected.

The original checkout was clean at entry. The study register was recorded before
the review, then its tracked diff and tracked/untracked status stayed identical
through both Claude invocations (`review-preservation.json`). Product/test paths
still match `5986c57`; only report/register/changelog/handoff/index documentation
is changed for delivery. E1 and E2 ran exclusively in disposable source copies,
both removed after checking their absolute workspace paths. No product benchmark,
full ordinary suite, installed/headed acceptance, push or commit was performed.
This documentation delivery does not change executable or test authority.

Study artifacts are under ignored `build/m1-7-ablation/`: `inventory.json`,
`diff-numstat.txt`, `commits.txt`, reviewer prompt/raw response/session receipt,
`experiment-plan.md`, `experiment.py`, `experiment-results.json`,
`experiment2.py`, `experiment2-results.json`, both ablation patches and six
control/ablation/fault logs. These are diagnostic provenance, not
replacement product acceptance artifacts.
