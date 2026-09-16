# M1-7 ablation implementation plan

## Active reassessment — test and evidence machinery (2026-09-17)

The user has redirected the task after R7-4: investigate materially larger
reductions in M1-7 test/evidence machinery, including retirement and reopening
deferred candidates. R7-5–R7-8 and R7-G execution is suspended during this study.
Existing product guarantees and historical acceptance are unchanged. Later
"Deliver now" wording records the prior implementation scope, not current
permission to resume it. Investigation does not authorize proposed deletions or
changes to evidence authority.

Baseline: clean `milestone1` at `95f31e1`. Finite corpus: original M1-7 changes
`40ca76f..5986c57`, integrated R7 changes through this baseline; added/changed
test, benchmark, validator, headed driver, JavaScript probe and artifact files;
their repository callers, CLI/CI consumers and owning active documentation;
deferred A6/A10/A11 and the relevant archived reduction dispositions. Product
source is inspected only to identify actual guarantees and test seams.

| ID | Investigation outcome | Closure evidence | Status |
| --- | --- | --- | --- |
| RI-1 | Census machinery and distinguish product, test, evidence and temporary study cost | Reproducible inventory.json/families.json and original/current deltas below | complete |
| RI-2 | Trace necessity and authority of major machinery families | Guarantee/consumer map, DEFENSE §7 classification and pinned historical replay below | complete |
| RI-3 | Compare larger retirement/replacement approaches | Options A/B/C, candidate populations, losses and retained detectors below | complete |
| RI-4 | Recommend a coherent reduced target and disposition of pending R7 rows | Proposal below; independent challenge resolved through pinned-contract and archive exit criteria | complete |

Only this register, M1_PLAN, CHANGELOG and HANDOFF may change for delivery.
Ignored evidence lives under `build/m1-7-ablation/reassessment/`, beginning with
its manifest. No production/test edits, benchmark runs, artifact rewrites, new
general harnesses or implementation commits. Source counts are diagnostics,
not proof of saved maintenance or runtime. Stop and report any supported hard
wall violation; otherwise close the named corpus and present one coherent
proposal without treating discoveries as implementation scope.

### Findings: the unit of reduction must be a capability

The previous plan optimized local duplication while preserving almost every
test/evidence capability. That is insufficient for the clarified goal. Original
M1-7 additions were 5,322/442 added/removed product lines and 16,097/272 test,
helper and evidence lines. R7-1–R7-4 changed product by +1/-77 and tests/helpers
by +214/-80: net **76 product lines removed, 134 test lines added**. The diff
does not move production algorithms into tests; it adds fixture separation and
retained behavioral witnesses. Nevertheless it has not reduced test machinery.
Documentation and ignored experiment scripts add further authoring/review cost.

Current benchmark producer (3,998 lines), independent validator (2,008) and
scale tests (1,866) total **7,872 textual lines**. Those three files dominate
the removable evidence architecture. Existing large service/host test files
also received M1-7 additions, but their whole sizes are not M1-7-owned deletion
populations. JSON byte volume is separate from source complexity. Counts are
reproducible in `build/m1-7-ablation/reassessment/inventory.json`; AST spans in
`families.json` describe candidate populations, not predicted net savings.

The main costs are distinct:

- **Maintenance:** multiple schemas and validation entrances, dual historical
  families, fabricated authority/install/runtime graphs, source rewriting and
  tests of those mechanisms.
- **Run time:** 35 cases × five fresh children = 175 measurement processes;
  15 additional readiness children. Keeping all cases and sample counts keeps
  most of the reported 70–90 minute full-run cost. No duration saving is measured.
- **Change procedure:** copying validators, constructing per-checkpoint fault
  matrices and proving unchanged intermediates can exceed the local code saving.
  These are temporary study costs, not shipped production code, but still matter.

### Authority versus machinery

DEFENSE §7 and PRESENTATION classify these fixed-profile budgets as Tier 2.
Preserving them requires genuine observations, declared fixture/profile/sample
counts, committed raw evidence and a separate validator. It does **not** require
the present readiness protocol, partial collection API, dual-family reader or
optional tracer. PRESENTATION currently prescribes several of those mechanisms;
change that owner explicitly before removing them. No policy is changed here.

| Family and current consumers | Value / removal consequence | Candidate population and disposition |
| --- | --- | --- |
| Separate untimed readiness: producer child modes, `run_readiness`, validator, terminal prerequisite and scale tests | Finds bad setup before a long run; supplies no measurement acceptance. Removing it may discover some failures later. | Six producer functions span 424 lines; readiness validator helpers span 106. Remove the readiness artifact, schema, coverage table and prerequisite together, not just its duplicated loop. Keep ordinary driver checks and each measured child's untimed setup/correctness checks. |
| Durable partial collection: producer index/state bookkeeping, `validate_collection_index`, interruption tests | Preserves independently inspectable accepted prefixes after interruption. It is explicitly **not resumable**. Losing this means less structured post-failure evidence, not false permission to accept an incomplete run. | Collection validator/error functions span 221 lines, producer helpers 29, plus interleaved loop state. Readiness/collection-specific test and fixture functions span 374 lines across both families. Retire accepted-prefix/next-or-failed state and public partial validation; retain failure logs/raw child outputs as diagnostics and publish a terminal artifact only after completion. Do not replace it with a journal. |
| Live legacy compatibility: v4/v5 family dispatch, old representation checker and historical-verdict test | Reproduces interpretation of old failed evidence; no product compatibility path. | The legacy representation function alone spans 125 lines, plus family branches/constants/tests. Archive reproducible interpretation at a pinned repository revision; current code handles only the new active family and refuses obsolete/mixed inputs. Preserve old artifact bytes, paths and verdict meaning. A pinned replay verifies historical interpretation, not a fresh run on an unavailable old environment. |
| Optional Plan-again tracer: `_plan_again_trace.py`, Setup/task parents and both children | Provides phase-level diagnosis through source rewriting and wrappers; snapshot validation is not a complete causal correctness proof. | Entire tracer is 529 lines; the trace-test region in `test_setup_headed.py` spans about 308 more, plus four consumer integrations. Retire the whole optional capability if its diagnostic loss is accepted. Preserve installed Plan-again outcomes, transport/replay tests and ordinary production-wrapper tests. R7-8's mirrored-oracle repair then becomes unnecessary. |
| Browser/native test scaffolding: renderer/app/modal probes, headed driver helpers and static prescription tests | Different probes reach different seams; similar fake DOMs do not establish redundant coverage. Some tests instead prescribe helper spelling or preserve accidental shared ordinals. | Reopen A6: delete the disconnected historical checkbox, use scenario-local deferred receipts, remove exact source-occurrence prescriptions after retaining executable driver refusals. Consolidate repeated confirmation setup locally. Do not build a universal fake DOM or delete entire browser/native layers by test-count comparison. |
| Actual measurement fixture/driver and independent verdict | Establishes the numerical claims and genuine installed endpoints. Most of this remains if all 35 SLOs remain. | Keep fixed large populations, fresh eligible plans, actual pending-frame/receipt endpoints, P95 **and maximum**, identity/membership and retained-memory classification. Simplify their surrounding representation, not the independent expected answers. |

Named function spans above are non-additive deletion estimates: some call-site
code is outside them, some shared setup survives, and replacement code is not
designed yet. The first three retirement families expose 905 lines of named
producer/validator bodies plus the 374-line test/fixture population; tracer
retirement exposes a separate 837-line module/test-region population before its
consumer edits. This is a materially larger surface than two local extractions,
but is **not** a promised 2,116-line net reduction.

Repository consumer search found no production caller of the benchmark or
validator. CLI entry points and direct scale tests are active consumers;
`NAMISYNC_M1_7_READINESS_PATH` also controls the ordinary real-artifact test.
No checked-in CI workflow was found. Manual external callers cannot be excluded.
Ignored R7 measurement scripts consume the current validator and must remain
bound to their recorded revision, not silently updated to the successor API.

### Options and recommendation

| Approach | What actually becomes smaller | What remains / decision required |
| --- | --- | --- |
| A. Retire optional capabilities, keep the current measurement data model | Readiness, partial-index state machine, legacy branches, tracer and their own tests disappear; A6 reduces brittle harness coupling. | Lower implementation risk, meaningful subtraction, but much of the 7,872-line scale system and 175-child cost remains. Explicit readiness/partial-diagnostic/tracer tradeoffs and archival decision required. |
| **B. One current acceptance path, with A's retirements — recommended under unchanged SLOs** | One fixed reviewed case specification, one authority record, one terminal raw artifact, one independent verdict path. Remove duplicate capability-specific contracts and synthetic fixtures instead of wrapping them in helpers. | Retain all 35 budgets/cases and fresh-process counts initially. Version the evidence contract and revise PRESENTATION mechanisms; keep physical source/wheel/install binding, runtime/profile identity, separate Git-normalized identity and independent semantic/statistical checks. This is a bounded evidence redesign, not a general benchmarking platform. |
| C. Rationalize the numeric acceptance contract as well | A smaller metric catalog can remove transition/setup branches and many fresh-process runs; the greatest possible deletion is retiring quantitative acceptance entirely. | Each dropped metric loses its specific current latency/memory claim. Structural tests and representative timings do not certify unmeasured variants. Requires a separate explicit product-acceptance decision, revised PRESENTATION/contract and new evidence for whatever remains. Historical P9 still describes its original bytes/profile. |

For B, freeze the reviewed declarative case specification by identity. Producer
and validator may read the same prescribed case IDs/budgets; the producer must
not generate or alter the expected answers. The validator independently owns
fixture expectations, endpoint witnesses and statistics. Sharing a generated
manifest or correctness function is not this simplification. Contract identity
and a separate verdict are essential; repeating every descriptive metadata
field in several parallel tables is not automatically independent evidence.

Concretely, the successor independent validator must contain the reviewed
contract digest (or an equivalently pinned immutable blob reference) outside
producer-supplied run files. It checks the loaded case table against that pin
before scheduling evidence can receive a verdict. A producer-supplied digest
matching its own edited table is insufficient. Fixture/endpoint expected
answers remain independently authored validator data or functions, not values
copied from observed child receipts. Changed budgets/case membership require
review and a new pinned contract, never automatic regeneration of the trust pin.

### Archival exit gate for B

The existing six JSON files remain at their original paths under
`tests/interfaces/web/`; this proposal does not rewrite, move or delete them.
The following exact interpreter blobs are recorded in their own authority
manifests and are reachable from repository history:

| Family | Existing artifact filenames (contract / authority / measurements) | Pinned validator | Reproduced historical interpretation |
| --- | --- | --- | --- |
| Legacy | `m1_7_plan_contract.json` / `m1_7_plan_authority.json` / `m1_7_plan_measurements.json` | Git blob `76a5ac04bae7618cd50ba59d85fc62b6140f3f52`, introduced at `ae3daf67` | Rejected: `plan-review maximum exceeds its fixed budget` |
| Compact P9 | `m1_7_plan_compact_contract.json` / `m1_7_plan_compact_authority.json` / `m1_7_plan_compact_measurements.json` | Git blob `5f5dfadbabaef47195cbca199b452d5b39fc7074`, present at `5986c57` | Accepted historical artifact, 35 observations |

Bounded replay command run during this investigation:
`.venv/Scripts/python.exe build/m1-7-ablation/reassessment/replay_history.py`.
It reads each pinned blob with `git cat-file blob`, verifies its Git object
identity, loads that validator, then calls its `validate_artifact` with the
unchanged contract, authority bytes, raw artifact and original authority receipt
Git identity. `historical_replay.json` records all six physical SHA256s and both
verdicts. Dependencies for this interpretation check were Git and CPython
3.13.14 standard library; it does not require or reconstruct the old installed
desktop/runtime. This reproduces the old verdict, not current-source acceptance
or a new timing run.

Before retiring active readers, preserve these blobs/artifacts/replay recipe
in an explicitly retained repository revision or verified archive with a manifest;
prove replay from that preserved material without the successor validator.
The **user's approval of this archival disposition** must explicitly decide
that old families no longer need validation by current ordinary tests. Update
PRESENTATION and M1_PLAN accordingly. Keep one bounded archive-integrity/verdict
check at migration, rather than porting old schemas into every future validator.
No archival exit decision has been granted by this investigation alone.

### Target execution shape

The terminal result should be the only acceptance-bearing run artifact.
Raw child outputs can remain useful diagnostics, without an accepted-prefix
schema or partial-inspection API. A failed/interrupted run has no accepted
terminal result. Keep subprocess isolation and timeouts; dropping a separate
readiness pass does not drop correctness checks inside each measured child.
Do not replace the removed protocols with configurable modes, resume support,
schema adapters or a shared producer/validator framework.

Before changing case count under C, distinguish runtime reduction from code
reduction. The six unchanged-after-sort cases already share one transition
implementation; removing five timing cases mostly reduces runs, not six drivers.
Changed search/filter/collapse/reset and numeric/name sort paths differ; no
worst-case dominance proof was established here. Likewise modal opening,
destructive confirmation, non-destructive Execute and control receipts have
different endpoints. Do not choose an arbitrary "representative ten" and claim
the other 25 budgets remain certified. If reducing the **majority** of all scale
machinery is the goal, that may require C; B cannot promise it while preserving
all genuine observations and provenance.

### Proposed boundary and verification for a replacement plan

1. Ratify B's retired capabilities and diagnostic tradeoffs in PRESENTATION and
   the parent delivery register, preserving numerical criteria and DEFENSE §7.
   Freeze historical v4/v5 source/artifact identities and reproducible verdicts;
   do not rewrite their files or make the current validator carry both forever.
2. Retire the optional tracer as one independent outcome, including its four
   consumers and trace-only tests. Ordinary production-wrapper and installed
   Plan-again outcome checks close this change; no new generic trace substitute.
3. Replace the evidence lifecycle as one coherent outcome: producer, current-only
   validator, direct scale tests and contract wiring. Delete readiness/index
   states and their bespoke test fixtures together. Review a before/after
   rule/state/artifact ownership map; reject mere forwarding or relocated logic.
4. Apply bounded A6 scenario/driver cleanup after the surviving harness shape is
   known. Leave product refactors A4/A5/A7/A8/A12 out of this test-machinery task.

Acceptance must follow retained guarantees, not the old machinery's entire API.
Keep a compact finite set of independent controls for wrong build/profile,
wrong fixture/endpoint, missing/duplicate/swapped cases or process identities,
bad sample type/count/order/correctness, P95-only and maximum-only rejection,
and incomplete terminal publication. Retired readiness/partial-index semantics
need no replacement detector once explicitly removed from the contract. Tests
for remaining product or safety guarantees still do: ST-5 is not a perpetual
one-to-one replacement obligation for tests of an intentionally retired feature.

Use focused/department gates for each changed surviving boundary, installed
headed tests when drivers change, ordinary/import checks at integration and
one full fresh run on the final versioned acceptance path. Reuse unchanged
passing evidence only with its actual dependency/byte identity. Do not run old
and new 70–90 minute suites at every helper commit or create a mutation framework
to prove every deleted line. Numeric contract changes under C would need their
own ratified gate, not this unchanged-SLO procedure.

**Pending R7 disposition:** supersede R7-5 and R7-8 if B is approved; they polish
capabilities being retired. Leave R7-6/R7-7 as optional production maintenance,
outside this clarified goal. Replace R7-G with the selected redesign's integrated
closeout after approval; do not claim its old full-current-source obligation has
already passed. R7-1–R7-4 remain delivered; do not spend another checkpoint
reverting their small changes before the larger ownership decision.

**Investigation limits:** source/AST/Git and repository consumer inspection,
with independent read-only policy and harness reviews, plus the bounded pinned
historical-interpretation replay above. No deletions, mutation experiments,
timing runs or new product correctness/current-source acceptance results. Unknowns are net
replacement size, actual run-time savings, external manual consumers and which
diagnostic/numeric capabilities the user chooses to retain. The recommendation
is reviewable design scope, not implementation authorization.

## Main objectives

Reduce duplicated receipt/retry logic and test setup cost while preserving the
delivered product, independent fault detection and truthful measurement evidence.
Remove two unused Plan-review mechanisms and unnecessary selection-resolution
work. Deliver small, independently reviewable checkpoints; leave admission,
representation and archival redesigns deferred.

Plan revision: 2026-09-17. The original study is committed in `dbeb7a5`;
its product/test baseline is `5986c57`. Study corpus: inclusive `ae3daf6..5986c57`
(diff base `40ca76f`). The user authorized consolidation on 2026-09-17,
including localized checkpoint measurements and one full run at closeout.
**Deliver now** below is the authorized implementation scope.
[M1_PLAN](M1_PLAN.md) is the parent delivery
authority; this document supplies its bounded maintenance subregister.

## Scope and decisions

The completion denominator is R7-1 through R7-8 plus R7-G. Candidate IDs A1–A12
remain stable for discussion; a candidate can be partially selected. Deferred
parts are excluded even when adjacent to edited code. No new product behavior,
public DTO/wire shape, safety policy, budget, general test framework, blanket
test deletion or M1-8 work is included. No LOC/test-count quota is a gate.

The baseline product is the behavioral reference. The previous delivery records
5,158 ordinary passes and accepted P9 evidence; this planning revision does not
claim to rerun them. Re-establish the relevant baseline before each implementation
checkpoint. A green rewritten suite alone is insufficient: pair behavioral
equivalence with independent fault detection at the boundary being simplified.

### How documentation constrains subtraction

| Kind | Authority and examples | Treatment |
| --- | --- | --- |
| Normative guarantee | AGENTS layering/scope/stops; DEFENSE hard walls and §7; BRIDGE ingress, identity/replay; PRESENTATION view/selection/sort outcomes and fixed criteria | Preserve. A conflicting simplification needs adjudication, not an assertion that the old test is obsolete. |
| Current mechanism | Full in-place projection replacement, comparator branches, duplicated receipt checks, test source-occurrence counts | May change within the named checkpoint. Trace each statement to the guarantee it serves, update its owner with the change, and retain a behavioral witness. A mechanism description is not automatically a permanent API promise. |
| Historical evidence | P9 frozen contract/authority/results, legacy failed evidence, E1/E2, earlier reduction reports | Preserve original bytes and interpretation. Do not rewrite history or pass old measured bytes off as new acceptance. |

Classify ambiguous sentences before editing. Public constructors, preview fields,
fresh execution checks, complete-request bounds, and independent validator
expectations are protected boundaries despite internal-looking implementations.
No direct caller does not prove an invariant has no coverage. Prior reduction
dispositions in TEST_ABLATION, TEST_REFINEMENT (especially ST-5),
PRODUCTION_REDUCTION and REDUCTION_FOLLOWUP remain context; do not reopen their
retired aggregate-retention model or erase same-level fault detectors.

### Failure and scope disposition

For a new red test, first compare its setup and expected result with the unchanged
baseline product and the normative contract. Reproduce in an isolated baseline
copy when needed; separate test defects, introduced regressions and latent
product defects. Do not change product behavior to satisfy an erroneous oracle,
and do not weaken an oracle merely to obtain green tests.

Correct checkpoint-introduced regressions within its declared boundary. For a
confirmed pre-existing product defect, retain a minimal reproducer, baseline and
candidate observations, consequence and owner in BUGS/HANDOFF and report it;
**do not fix it in this refactor**, including under AGENTS' otherwise available
bounded-pre-existing-fix allowance. An affected gate stays blocked pending a user
decision; independent authorized rows may continue unless an always-stop applies.
Never silently xfail, skip or relabel the failed guarantee. Follow AGENTS'
second-instance/third-defect recurrence stops and exact-state recovery rules;
supported data loss, unauthorized/duplicate effects, hard-wall escape and false
success require immediate stop and preservation. Findings do not add checkpoints.

## Investigation and regression map

The original investigation used diff/AST inventories, selected caller/contract
tracing, two Codex sidecars and one independent Opus 5 xhigh session. It was not
an exhaustive line review. Revalidate symbol references against the implementation
base; line references below describe `5986c57`, not permanent locators.

| Boundary / finite family | Failure introduced by simplification | Detection owner |
| --- | --- | --- |
| Synthetic authority controls versus actual fixture generators | Frozen data makes live drift tests tautological; mutable expected data leaks between cases | R7-1: independent frozen expectations, live drift mutations, cohort isolation |
| Canonical sibling order and PlanReviewState acquisition/selection/view publication | Wrong tie/order, removed constructor validation, stale cached order, partial revision publication | R7-2/R7-3: workflow and real registry/view consumers |
| Partial/readiness/terminal evidence validators | Shared helper loses boundary-local uniqueness, provenance or completeness rejection | R7-4: identical corruption corpus through applicable public validator entries |
| Producer child-to-receipt-to-index transition | Interrupted publication claims acceptance or loses prior receipts; readiness becomes measurement | R7-5: failure matrix around exact publication boundaries |
| Browser start/replay/manual-retry chain | New logical command or payload, renewed auto-replay allowance, loss of existing command-specific checks | R7-6: packaged production wrappers and installed flows; foreign-task Execute-result rejection remains F1's separate investigation |
| Service ID resolution before authoritative selection mutation | Lazy work changes mixed-ID/folder safety, exception order or replay behavior | R7-7: baseline differential behavior plus counted service witnesses |
| Optional trace transformation oracle | Rewritten test accepts a no-op transform or shares its mistake with production | R7-8: independent splice/trace assertions and seeded transformer faults |
| Cross-checkpoint measurement authority and installation | Tests pass against stale or self-certified evidence | R7-G and every affected commit: immutable lineage, current-source evidence disposition |

### Study census and strength

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

## Candidate register

| ID | Candidate | Deliver now | Deferred / reopening condition |
| --- | --- | --- | --- |
| A1 | Validator-local receipt checks | R7-4: common receipt invariants, independent oracle retained | No producer/validator merger or schema change |
| A2 | Producer publication bookkeeping | R7-5: one local receipt publication operation | No generic runner, recovery/resume or readiness/measurement merger |
| A3 | Synthetic/live fixture separation | R7-1: distinct providers and independent live-drift witnesses | No reduced live fixture populations |
| A4 | Browser admission retry | R7-6: shared mutation-admission replay algorithm | Read retry extraction and app settlement consolidation deferred as separate outcomes |
| A5 | Service selection admission | None | Entire concurrency/effect refactor deferred; needs separate race/ownership design and ratification |
| A6 | Test scenario coupling and source prescriptions | None | All three independent cleanups deferred, including disconnected checkbox; individually scope same-level detectors before adoption |
| A7 | Internal selection transfer snapshot | None | Later ratification in ARCHITECTURE/PRESENTATION and M1_PLAN; public preview compatibility and freshness must be designed first |
| A8 | Stable topology plus selection overlay | None | Separate measured hotspot/design decision; no overlay/cache/map-copy redesign here |
| A9 | Unused mechanisms | R7-2 comparator; R7-3 unused replace_projection route | No public-constructor validation removal or new order framework |
| A10 | Legacy validator retirement | None | Entire archival disposition deferred; active historical validation stays |
| A11 | Tracer oracle | R7-8: remove mirrored transformation calculation only | Tracer retirement and four consumer rewrites deferred pending diagnostic-loss decision |
| A12 | Repeated safety derivation | R7-7: lazy resolver work only, retaining authoritative workflow checks | Cross-call/workflow-wide safety reuse deferred; no new context object, cache or bypass parameter |

## Checkpoint register

Order favors the bounded fixture/comparator changes first. Dependencies are
acceptance dependencies; ordinary shared-file conflicts are not permission to
combine outcomes. Every implementation row includes its owned tests/docs and
evidence disposition. R7-G is the final completion gate, not a place to postpone
an otherwise-required checkpoint gate.

| ID | Accepted outcome | Depends on | Primary verification | Status |
| --- | --- | --- | --- | --- |
| R7-1 | Separate synthetic manifests from real generator observations (A3) | Startup `ee8d861` | Full scale-test module; synthetic generator trap and live population/order faults | complete |
| R7-2 | Replace obsolete canonical comparator with direct key (A9) | Startup ee8d861 | Projection/review tests; reversed-order fault and all real sort modes | complete |
| R7-3 | Remove unused in-place full projection replacement (A9) | R7-2 | Acquisition, selection, new-view and failed-publication witnesses | complete |
| R7-4 | One validator-local implementation per common receipt invariant (A1) | R7-1 | Partial/readiness/terminal corruption matrix and independent oracle controls | complete |
| R7-5 | One producer-local receipt publication operation (A2) | R7-4 | Publication/index interruption matrix; independent validator accepts/refuses exact artifacts | pending |
| R7-6 | One browser admission-replay state machine (A4) | Implementation authorization | Real bridge retry matrix, transport/consumer and installed headed gates | pending |
| R7-7 | Avoid unused safety derivation during ID resolution (A12, partial) | Implementation authorization | Selection/service differential cases and derivation witnesses | pending |
| R7-8 | Independently test optional trace transformation (A11, partial) | R7-6 | Restoration, no-partial-write and deliberate transformer faults | pending |
| R7-G | Close integrated behavior, detector quality and evidence lineage | R7-1–R7-8 | Ordinary/import, affected installed/headed, current-source quantitative disposition and adversarial sweep | pending |

## Candidate evidence and retained boundaries

The following entries retain the study's detailed evidence. The candidate
register above and checkpoint specifications below narrow what is deliverable;
suggestions in a deferred entry are not implementation instructions.

### A1 — Consolidate within the validator, preserve oracle independence

**Disposition:** Deliver now: R7-4 only.

`tests/interfaces/web/_plan_review_scale.py:520` checks measurement receipt
shape, case, runtime, sample population, correctness and numeric fields during
collection inspection. Terminal paths repeat them at `1674` and `1723`;
readiness checking overlaps at `362` and `564`. R7-4 consolidates common receipt
invariants locally while preserving the independent oracle and each boundary's
path/hash, uniqueness and completeness duties.

### A2 — Consolidate evidence publication, not readiness and measurement

**Disposition:** Deliver now: R7-5 only.

`tests/plan_review_benchmark.py:3409` and `3592` repeat child-result checking,
canonical receipt publication, staging removal, hashing, wrapper/index entries,
attempt advancement and incomplete retention. Index publication is already
shared. R7-5 extracts receipt persistence/accepted-attempt bookkeeping only;
readiness and measurement still have distinct plans, watchdogs, schemas and
fresh-process obligations.

### A3 — Make validator controls independent of expensive fixture realization

**Disposition:** Deliver now: R7-1. The E2 patch is evidence, not an integration patch.

`test_plan_review_scale.py:430` caches live manifests for both fixture families.
Synthetic `_authority_inputs` (`438`) uses them despite fabricating other runtime
and source bytes. Manifest construction through `plan_review_benchmark.py:288`
and `3277` builds full projections/review state. Live checks at `1175` and `1233`
must retain actual generator observations against frozen expectations.

E2's five selected controls passed before and after frozen-manifest substitution
with live generation forced to raise; a missing maximum-budget rejection was
detected. Single-run timings were 17.48 s and 0.28 s, diagnostic only. Its patch
changes a provider also used by live tests and is **not integration-ready**.
R7-1 splits the providers and separately proves live drift detection. Existing
process caching means these timings cannot be extrapolated as per-test savings.

### A4 — Give admission replay one implementation

**Disposition:** Deliver now: R7-6 admission retries only; read-retry extraction is deferred.

`namisync/interfaces/web/assets/bridge.js:677` (`submitStart`) and `798`
(`startExecution`) duplicate uncertainty classification, an automatic-replay flag
and exact manual-retry closure. R7-6 shares that algorithm while retaining the
existing command validators, payload construction and timeout choices. The
mocked Execute wrapper in `task_shell_probe.mjs:140` is insufficient evidence;
the real bridge probes must execute production `startExecution`.

### A5 — Share selection admission, retain distinct task and general wrappers

**Disposition:** Deferred in full. No service admission or lifecycle consolidation in this plan.

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

**Disposition:** Deferred in full. Each bullet is a separate potential future outcome.

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

**Disposition:** Deferred for later ratification; no internal/public selection transfer changes now.

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

**Disposition:** Deferred in full; requires evidence of a material allocation hotspot and a reviewed design.

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

**Disposition:** Deliver now as two atomic outcomes: R7-2 and R7-3.

`web/plan_review.py:234` contains a 44-line `replace_projection` with four
test callers (`test_plan_review.py:127`, `270`, `477`, `498`) and no found
production caller. `TaskRegistry.open_plan_view` (`drain.py:753`) and staging
memory evidence acquire a fresh state. Removing the unused method must preserve
useful constructor, gesture, exhaustion and failed-publication coverage; active
ARCHITECTURE/PRESENTATION wording needs precise mechanism updates.

Separately, `workflows/plan_projection.py:400` alone calls `_compare_nodes`
(`917`), always PATH/ASCENDING; real sorts use the algorithm at `414`. R7-2
uses `(rel_path_key, node_id)` and removes unreachable comparator branches.
E1 recorded 33 passes before/after and a causal failure for a reversed canonical
key in an isolated copy. It supplies bounded support, not current full-suite,
headed or quantitative acceptance. R7-3 is a separate commit outcome.

### A10 — Archive legacy interpretation instead of carrying it forever

**Disposition:** Deferred in full; keep current historical-evidence validation.

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

**Disposition:** Deliver now: R7-8 oracle only. Instrumentation retirement is deferred.

`_plan_again_trace.py:317` supplies 18 replacement anchors across three assets;
the transformer is at `344`. `test_setup_headed.py:305` mirrors its regex/newline/
replacement algorithm from the same table, weakening independence. R7-8 replaces
only that oracle. The Setup/task-shell parents and both child drivers remain
four live consumers. Trace validation (`502`) checks vocabulary/shape, not a
complete causal success sequence. Retirement would lose diagnostics and remains
a separate decision; hashes alone do not prove correct instrumentation.

### A12 — Reuse safety facts within a selection mutation

**Disposition:** Deliver now: R7-7 lazy resolver only. The broader workflow-owned reuse proposal below is deferred.

Direct tracing of the fresh successful mutation at `service.py:965` finds two
unconditional pristine derivations in ID resolution (`967`, `972`), one inside
`apply_selection_mutation` (`workflows/selection.py:220`) and one for the final
decision (`service.py:983`, `selection.py:133`). Resolver derivation computes
digest/risk/byte facts merely to get folder-toggleable membership.

R7-7 removes only unused resolver work. Sharing safety facts across resolver,
mutation and final decision is deferred: it requires a narrow workflow-owned
operation without bypassing public validation or admitting unchecked safety maps.
No retained cache/context framework is included. The depth-32 benchmark helper
(`plan_review_benchmark.py:405`) calls `derive_execution_selection` directly;
it is not a measurement of the four-derivation service gesture. No latency gain
or one-derivation-per-mutation result is promised.

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

## Detailed checkpoints

### Startup baseline and working-set rules (2026-09-17)

Start from clean `milestone1` at `d91871f`, the sole checkout. The diff from
`5986c57` contains documentation only; product, tests and frozen evidence are
unchanged. Python is the project venv's 3.13.14; Node is available on PATH.
Historical 5,158 ordinary passes and P9 are reference evidence, not new runs.
Baseline each checkpoint's named neighborhood before its first implementation;
run the ordinary suite once at integrated closeout, or earlier if impact becomes
broad or uncertain. Keep checkpoint department, fault-control and headed gates.

The working set is the eight accepted rows and final sweep; deferred candidates,
F1 hardening, M1-8, push and PR remain excluded. Startup documentation owns this
plan, M1_PLAN, PRESENTATION, CHANGELOG and HANDOFF. Expand each implementation
row's exact files and consumer/detector map before edits. No product changes
precede startup baseline classification and measurement-policy review.

New evidence belongs only under ignored
`build/m1-7-ablation/implementation/<checkpoint>/`; `startup` owns baseline and
policy review. Each directory begins with `manifest.md` naming base/candidate,
permitted artifacts, commands and cleanup. Use descriptive `.txt` logs, `.json`
receipts, `.patch` fault controls and disposable `control-*` source copies.
Preserve all pre-existing evidence; retain new raw evidence through closeout.
Remove only positively identified disposable copies after results and patches
are retained. No permanent generic measurement or mutation framework is added.

### Shared execution and evidence rules

Each row names a bounded behavioral family, not an exhaustive edit list. Its
direct imports, fixtures, source-anchor consumers and subject descriptions may
be updated to complete that same outcome; record discovered direct consumers
before editing. A new algorithm, ownership change or independently useful
cleanup is not incidental work. Keep deferred candidates out of each diff.

Before editing, record the base revision, exact selected test nodes, expectations
being retired and their surviving detectors, subject-document classifications,
and the row's source/evidence dependency disposition. Run unchanged controls.
After editing, rerun those controls and the specified owning departments. Existing
tests may be parameterized or removed only with an explicit mapping from each
protected behavior to a surviving witness; implementation spelling alone is not
a protected behavior. A new helper must reduce real duplicated logic rather
than hide it behind callbacks, mode flags or a generic framework.

Fault controls use isolated task-owned copies under ignored
`build/m1-7-ablation/implementation/<checkpoint>/`, with a manifest, patches,
commands, baseline/candidate identities and results. Never mutate the accepted
checkout or installed user app to seed faults. A mutant must reach the named
boundary and fail its causal assertion; import errors, timeouts and setup crashes
do not count. Restore the unmutated candidate and verify it passes. Include a
harmless structural variation where coupling is being removed. Do not add a
permanent mutation framework or exhaustive Cartesian test matrix.

Commands below run from the repository root in native PowerShell. `pytest`'s
ordinary default excludes headed tests. Use the already configured supported
Node runtime; required JavaScript gates cannot skip. Retain stdout, exit codes
and unexpected skips. Department ownership comes only from `tests/_departments.py`.

```powershell
# S: receipt/fixture family
.\.venv\Scripts\python.exe -m pytest -q tests/interfaces/web/test_plan_review_scale.py
# P: canonical order, state and real registry consumers
.\.venv\Scripts\python.exe -m pytest -q tests/test_plan_projection.py tests/interfaces/web/test_plan_review.py tests/interfaces/web/test_drain.py
# B: production bridge wrappers plus source-anchor consumers
.\.venv\Scripts\python.exe -m pytest -q tests/interfaces/web/test_transport.py tests/interfaces/web/test_frontend_static.py tests/interfaces/web/test_setup_headed.py
# M: selection workflow/service/desktop neighborhood
.\.venv\Scripts\python.exe -m pytest -q tests/test_bridge_service.py tests/test_bridge_selection.py tests/test_workflows.py tests/interfaces/web/test_drain.py
# T: ordinary trace transformation and delegation controls
.\.venv\Scripts\python.exe -m pytest -q tests/interfaces/web/test_setup_headed.py
# I / WI: checkpoint closure, chosen below by ownership
.\.venv\Scripts\python.exe -m pytest -q --dept interfaces
.\.venv\Scripts\python.exe -m pytest -q --dept workflows --dept interfaces
# H: required when desktop behavior, packaging or headed harness changes
.\.venv\Scripts\python.exe -m pytest -q --dept interfaces -o "addopts=" -m headed
# O / L: integration, and earlier when blast radius is broad or uncertain
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\lint-imports.exe
```

**Q — localized checkpoints, full closeout.** User-approved on 2026-09-17:
R7-1–R7-8 use Q-local, a DEFENSE §7 Tier 1 current-source drift guard, before
each commit. R7-G runs Q-final once: the existing full fresh authority, readiness,
35-case/175-child measurement and independent terminal-validation procedure.
Local passes permit checkpoint commits but do not renew full scale acceptance.
P9 remains historical evidence for its original bytes. Full acceptance stays
pending until Q-final; partial runs are never pooled into its terminal artifact.
Budgets, profile, fixture populations, five fresh children per selected metric,
warm sample counts, maximum and P95 are unchanged. Failed guards block their row;
do not retry away a failure, narrow the selected set after observing results,
or defer an introduced regression to closeout.

Before each row, freeze its affected metric IDs and dependency rationale,
baseline/candidate hashes, exact commands, installed wheel/source byte bindings,
runtime/profile, raw output paths and independent checking procedure. Run only
the cases whose measured execution changes, including direct consumers. If the
change affects only synthetic controls or parent/validator bookkeeping, run the
affected live fixture, corruption and publication controls; explicitly record
why timing cases are unaffected. Tests-only is not an automatic exemption.

The current full validator admits no subsets. Q-local therefore uses existing
`--component-child` / `--headed-child` commands for selected fixed metric IDs
with unique launch tokens and output paths. A bounded task-owned script may
select those metric definitions in memory and call the independent validator's
`_validate_children` with actual hashed receipts and frozen headed runtime.
It must check exact selected membership, counts, correctness, identity, maximum
and P95; retain raw receipts and dispersion. It is not a terminal validator or a
new permanent contract family. Validate source/wheel/install and profile identity
separately before and after collection. Never pass synthetic receipts as measured
observations. Existing full contract and historical artifacts remain immutable.

| Row | Q-local dependency neighborhood (freeze exact cases before edits) |
| --- | --- |
| R7-1 | Synthetic/live provider isolation, live population/order/retained-buffer and maximum-only controls; no changed timed code. |
| R7-2 | `projection_incremental_retained_memory_staging_overlap`, five fresh children; canonical construction is outside cold-build and warm-sort timers. Real-sort behavior remains covered by P. |
| R7-3 | No timed IDs: deleted route has no product/benchmark caller, import precedes the memory baseline, and measured acquisition/update/selection bodies remain unchanged. P/WI/L/H and three copied faults remain required. |
| R7-4 | Public partial/readiness/terminal corruption equivalence against baseline validator; no changed timed child code. |
| R7-5 | Real receipt/index publication failure matrix and independent validation; no changed timed child code. |
| R7-6 | Installed headed Execute feedback/receipt; include other bridge consumers if their measured path changes. |
| R7-7 | Installed headed selection gesture; direct depth-32 helper does not measure service ID resolution. |
| R7-8 | Diff against frozen inputs and trace consumers; no timing run when only independent ordinary oracle changes. |

Record a new immutable authority/result lineage and preserve the accepted P9 and
legacy bytes at their original meanings. Freeze candidate hashes before running;
archive the validator revision as well as its identity. A candidate validator
cannot certify its own equivalence: run the shared corruption corpus against the
baseline and candidate public entry points. Preserve the old validator for its
historical evidence rather than altering it retroactively. Subject-owner updates
and the new artifact references belong in the same checkpoint commit. Exact
versioned artifact filenames/install paths are selected and recorded before
freezing; do not overwrite the accepted compact files to make a test green.

The existing producer CLI supports `--freeze-authority`, `--run-readiness` and
`--run-gate`, each with `--contract`, `--source-root`, `--installed-root`,
`--installed-wheel`, `--benchmark-root`, `--output` and the truthful workload
confirmation; readiness adds `--authority`, measurement adds `--authority` and
`--readiness`. The independent `_plan_review_scale.py` CLI accepts `--contract`,
`--authority`, `--readiness`, `--measurements`, `--source-root`,
`--installed-root`, `--installed-wheel`. Record the fully resolved command lines
in the row before execution, including the supported installed Python runtime.
Q-final has two phases: freeze and validate candidate observations before creating the
closeout commit; then use `validate_committed_source_workspace` to check that
commit's clean HEAD/source/evidence identity before integration, dependent
implementation or marking the row complete. Also check source/wheel/installed
physical bytes and Git-clean identity, including P9's supplemental
`core/execution.py` binding. Checkpoint gates below mean Q-local; check their
recorded source hashes against committed HEAD after each commit. R7-G requires
both Q-final phases. On mismatch preserve the
exact commit, artifacts and discrepancy, stop dependent work, and classify it
under the failure/scope policy. Never amend away the evidence or use a later row
to certify different bytes. The existing real-artifact pytest gate targets its
configured artifact paths; a skip or validation of historical paths is not Q for
a new lineage. Version its narrow artifact wiring with the evidence if needed.

No performance gain is claimed by this plan. E1/E2 timings are historical
diagnostics. Complexity claims require the source-derived argument and counted
witnesses required by DEFENSE §7, not elapsed-time assertions.

### R7-1 — Isolate synthetic fixture expectations (A3)

**Delivery evidence.** Synthetic authority inputs now receive deep copies of
cached frozen compact expectations; both live families still generate actual
manifests, compare counts/order/retained descriptors and check actual sibling
sorts against frozen orders. S: 55 passed / 1 historical-artifact skip. I: 1,673
passed / 1 skip / 3,519 deselected. The skip remains unconfigured historical
readiness, not current quantitative acceptance. Task-owned TEMP caused custody
source-tree cache refusals; the normal external TEMP run passed without code
changes. Isolated copied-source population, order, retained-descriptor and
maximum-only faults fail their causal assertions; harmless metadata passes.
The synthetic generator-trap cohort passes all 41 cases (30 named functions).
Evidence and exact patches/commands:
`build/m1-7-ablation/implementation/r7-1/manifest.md`. Q-local selects no timed
case because production, generator and validator bytes are unchanged. Full
scale acceptance remains pending R7-G. Fresh adversarial review approved the
actual diff and corrected evidence; documentation links and diff checks pass.
Commit: `test(presentation): Separate synthetic and live scale fixtures`
(the commit containing this record).

**Objective.** Remove full product fixture construction from synthetic validator
and collection-failure controls, so their expected answers stay independent.

**Startup expansion.** Base `d91871f`; production/producer/validator population
is empty. Edit only `tests/interfaces/web/test_plan_review_scale.py` plus this
register, PRESENTATION, CHANGELOG and HANDOFF. `_fixture_manifests` has exactly
three direct consumers: `_authority_inputs` and the two live gates below.
Synthetic `_authority` consumers cover readiness, collection failure, authority
and terminal corruption. Preserve their assertions through a fresh-copy provider;
keep the live gates on actual generated manifests. The frozen compact authority
is an input oracle, never an output to rewrite. ST-5's same-level detector rule
and E2's shared-provider exclusion remain binding. The unchanged S baseline is
54 passed / 1 skipped (30.61 s); the real-artifact skip lacks configured readiness
and is not Q. Q-local has no timed metric: only this ordinary test helper changes.
Gate: S + I, generator trap/copy isolation, three independent live drift faults,
maximum-only public-validator fault and harmless structural variation, then fresh
review. One atomic R7-1 commit owns all provider changes and evidence mapping.

**Scope and approach.** In `test_plan_review_scale.py`, split the manifest provider
used by `_authority_inputs` and its synthetic authority/readiness/artifact/
corruption/collection-failure consumers from the provider used by actual live
generator checks. Give synthetic consumers fresh deep copies of frozen compact
expectations. Keep actual base and information-heavy fixture construction in
the population/order/retained-representation family. Product, generator and
validator behavior are unchanged; do not apply E2's shared-provider patch.

**Acceptance criteria.** Synthetic controls run with real fixture generation
forced to raise. Live checks still observe generated populations, ordering and
retained buffers against separately frozen expectations. Mutating one synthetic
copy does not affect another. Both fixture families retain their actual declared
populations; no authority is inferred from the generator's own output.

**Regression watchlist.** Shared helper redirection can make live tests compare
frozen data with itself. Cached mutable manifests can contaminate later cases.
Frozen data can accidentally supply acceptance-run observations. Catch these in
provider isolation and actual generator consumers, not only helper unit tests.

**Tests and evidence.** S then I and Q. Explicit live gates:
`test_plan_review_fixture_realizes_exact_counts_depth_duplicates_and_orders`
and `test_plan_review_fixture_expected_orders_match_actual_sibling_sort`.
Seed separately a realized population drift, incorrect order and retained-buffer
descriptor drift; each corresponding live witness must fail. Retain E2's
maximum-only validator fault control through a synthetic public-entry test.
Preserve exact cohort node lists and positive/negative results.

**Documentation and handoff.** PRESENTATION distinguishes synthetic controls
from actual observations; record the provider split, oracle origins and new
evidence lineage. Update row status, CHANGELOG and HANDOFF.

**Adversarial review.** Trace every old-provider consumer to its new provider.
Reviewer must establish that no live observer now returns its expected result
and that the fault controls do not modify both sides of a comparison.

**Commit gate.** All above checks, baseline and Q pass before
`test(presentation): Separate synthetic and live scale fixtures`.

### R7-2 — Remove obsolete canonical comparator (A9, first outcome)

**Delivery evidence.** Canonical siblings now use the direct
`(rel_path_key, node_id)` key; the unused comparator branches, helper and import
are removed. Real-sort code and public validation are unchanged. P: 169 passed;
WI: 2,480 passed / 1 historical-artifact skip; L: all 12 contracts kept.
Q-local independently validates five fresh memory/staging children per revision:
baseline maximum 278,835,200 bytes, candidate maximum 285,605,888 bytes against
335,544,320 bytes. Across-child ranges are 2,371,584 and 2,609,152 bytes.
The candidate maximum is higher; this is a fixed-budget drift pass, not a memory
improvement claim. Before/after authority and supplemental execution bindings
match in each phase. Sandbox native-probe and pip-cache setup issues occurred
before samples; bounded desktop-capable execution and no-cache installation
resolved them. A checker hash-case mismatch was corrected and the same raw
baseline receipts revalidated, without recollection or budget changes.
Evidence: `build/m1-7-ablation/implementation/r7-2/manifest.md`. Copied old
source passes the three new edge cases; candidate passes four controls; the
reversed-key mutant fails its canonical-order assertion with loaded-copy identity
recorded. Fresh adversarial review approves code, documentation and actual
evidence. Commit: `refactor(workflows): Simplify canonical Plan ordering`
(the commit containing this record).

**Expansion refreshed at `efb5dc7`.** Production population:
`namisync/workflows/plan_projection.py` only. Tests: existing projection/review/
drain family, with `tests/test_plan_projection.py` additions only for uncovered
tie/empty/single-child behavior. Docs: this register, CHANGELOG and HANDOFF;
PRESENTATION only if mechanism prose changes. Direct consumers are the workflow
facade, `PlanReviewState` acquisition/replacement and the benchmark's construction
helpers. No caller of the removed comparator exists outside its sole canonical
sort adapter. E1 is historical support; repeat its causal reversed-key mutant.
The unchanged P baseline is 166 passed in 1.85 s. Preserve real-sort implementation
and topology validation; gate P + WI + L, reversed-order control and Q-local,
then independent review and the single commit below. R7-1 changed only the recorded scale test and docs; all product/benchmark seams
remain identical to the inspected revision. Its edit cannot authorize population expansion.

Q-local samples only `projection_incremental_retained_memory_staging_overlap`:
the memory interval includes canonical state construction. Cold metrics time
`build_plan_projection` without sorting; warm sort factories construct canonical
state outside timing, then use the untouched cached/real-sort path. No claim
about their timing follows from this removal. Baseline/candidate installations,
resolved commands and manifests must be frozen under
`build/m1-7-ablation/implementation/r7-2/measurement/{baseline,candidate}/` before
editing; each owns its wheel, clean venv, five raw child receipts and checker
result. `--installed-root` means the venv's `Lib/site-packages`, not the venv root.

**Objective.** Express the sole canonical PATH/ASCENDING order directly without
an unused multipurpose comparison implementation.

**Scope and approach.** `workflows/plan_projection.py`: replace the sole
`_compare_nodes` adapter with `(rel_path_key, node_id)`; remove only its now-unused
branches/helpers/import. Keep the separate real-sort algorithm and public
validation unchanged. No new sorting facade or representation.

**Acceptance criteria.** Canonical sibling order and inverse ranks match baseline;
all real sort directions, unavailable-last, raw filename/numeric values, ties,
identity and hierarchy remain unchanged. The removed machinery has no remaining
caller. No change in selection, execution order or public shapes.

**Regression watchlist.** Preorder may differ from lexical order; identical keys
need deterministic tie behavior; descending real sort must not inherit a reversed
canonical tie-break. Catch these through real workflow output and review windows.

**Tests and evidence.** P then WI, L and Q. Retain
`test_canonical_order_does_not_assume_source_preorder_is_lexical` and
`test_trusted_sort_matches_explicit_orders_for_all_real_sorts`. Repeat E1's
reversed-key fault on the current candidate and observe the order assertion fail.
Characterize ties and empty/single-child cases where existing coverage is absent;
do not replace independent expected orders with calls to the new key helper.

**Documentation and handoff.** PRESENTATION mechanism wording only if affected;
record caller search, behavioral evidence and Q lineage in this row/HANDOFF.

**Adversarial review.** Reviewer traces the sole old caller and all real-sort
branches and verifies comparator retirement removed no live behavior.

**Commit gate.** All above checks and baseline pass before
`refactor(workflows): Simplify canonical Plan ordering`.

### R7-3 — Retire unused in-place full projection replacement (A9, second outcome)

**Delivered.** Only the unused method was removed. Four test consumers were
migrated to selection refresh, fresh acquisition and surviving exhaustion paths;
failed selection transformation preserves the complete prior view. Final P171,
WI2482/1 historical-artifact skip, L12 and installed H30 pass. Four copied
candidate controls pass; reset sort, malformed text, malformed topology and early
publication faults fail their named retained assertions. Independent review
approved source, assertions and evidence hashes. Exact commands, patches, loaded
paths and raw logs are in `implementation/r7-3/manifest.md`. No timed child body
changed, so Q-local uses the declared no-timing decision; Q-final remains open.

**Expansion refreshed at `884813d`.** Product population is only
`namisync/interfaces/web/plan_review.py`; tests only
`tests/interfaces/web/test_plan_review.py`. The four direct test calls are
gesture refresh, malformed acquisition/replacement, order invalidation and
revision exhaustion. No production/benchmark caller exists. Inspect
`TaskRegistry.open_plan_view` (fresh state before guarded publication) and its
`replace_selection` consumer without changing the registry. Docs: ARCHITECTURE
and PRESENTATION mechanism wording, this register, CHANGELOG and HANDOFF.
R7-2 changed only the canonical sort key and added edge tests; constructor and
registry seams remain otherwise identical to the read-only `efb5dc7` study.
Baseline P169 and WI2480/1 skip from the identical integrated candidate remain
valid; R7-2 committed-source check passed. Existing malformed constructor,
failed update and selection tests preserve same-level detectors under ST-5;
E1 is not a substitute for these active-route checks.

Migrate gesture assertions to actual selection changes, retaining search,
filter, chosen sort, collapse, selection/window facts and both revisions. Keep
malformed-constructor assertions and retire only the unsupported replacement
half. Replace old order-invalidation test with fresh-state order/view identity.
Migrate exhaustion to selection and check other surviving revision transitions;
refusal preserves summary and window. Keep failed-update publication and add a
focused failed-selection-transform witness if absent. Copied-source faults must
reset selection sort, admit malformed acquisition and publish before a forced
transform failure, each failing the named ordinary assertion. Freeze exact
nodes/patches/commands in `implementation/r7-3/manifest.md` before editing.

Q-local has no timed IDs: benchmark `make_plan_review_state` and memory staging
construct fresh states, then use active update/window paths; none calls the
removed method. Its class code is imported before the memory baseline. This
decision applies only to strict deletion plus test migration. Gate P + WI + L + H,
the retained/migrated detectors and three isolated fault controls, subject-doc
checks and fresh review close one atomic R7-3 commit. Full Q-final remains due.

**Objective.** Remove an unused state publication route while preserving every
currently supported acquisition, selection and view-update guarantee.

**Scope and approach.** Remove `PlanReviewState.replace_projection` and migrate
the useful assertions in its four direct test callers. Inspect `TaskRegistry`'s
`open_plan_view` consumer; it continues to construct a fresh state. No registry
redesign or changes to public projection/visible-sequence constructor validation.
Depends on R7-2 only for the canonical-order baseline.

**Acceptance criteria.** Fresh acquisition validates malformed topology and owns
fresh orders/view identity. Selection updates retain filter/search/collapse/sort
and authoritative facts. Surviving revision-changing operations refuse exhaustion
before publication; failed transformations leave prior summary/window usable.
No production caller depends on the retired method. Conditional retained-sort
and atomic rebuild guarantees remain wherever a rebuild is supported.

**Regression watchlist.** Deleting all four tests loses constructor and gesture
coverage; testing only new acquisition misses failed-update publication. Preserve
the constructor half of malformed acquisition, move gesture assertions to
`replace_selection`, and exercise surviving revision transitions explicitly.

**Tests and evidence.** P then WI, L, H and Q. Retain
`test_plan_review_state_refreshes_selection_without_resetting_view_gestures`,
`test_plan_review_validates_projection_structure_at_acquisition` and
`test_plan_review_state_retains_complete_view_when_update_rebuild_fails` in
behavioral form. Fault controls: reset sort during selection, admit malformed
topology, and publish state before a forced transform failure. Exhaustion refusal
must preserve summary/window. Record the retired-to-surviving assertion map.

**Documentation and handoff.** Update ARCHITECTURE/PRESENTATION references to
in-place replacement to describe actual acquisition/selection routes; retain
their normative sort/publication guarantees. Record unsupported-route retirement
and evidence, without generalizing it to inventory's future rebuild design.

**Adversarial review.** Search production, test helpers and measurement staging
for consumers. If removing this method requires redesigning a supported rebuild
route, stop this row for scope adjudication rather than expanding it.

**Commit gate.** All above checks, Q and baseline pass before
`refactor(presentation): Retire unused projection replacement`.

### R7-4 — Consolidate common receipt validation (A1)

**Delivered.** Four shared rules now each have one implementation: readiness
receipt keys (two callers), measurement receipt keys (two), process identity
shape/type/range (three), and sample shape/correctness/value (two). Boundary
callers retain distinct decisions and refusal categories. A two-comparison
forwarding helper was rejected and removed. No direct tests, producer, timed
child, schema or historical artifacts changed. Final S55/1 skip and I1675/1 skip
pass on SHA256 `7A5CB498048DF3C9F4D007A712588A3BAE726DF50CF0E5E9381318ADF1E5A067`.
The 59-case public-entry corpus agrees with frozen baseline; real harmless
process-ID variations pass, and correctness/reused-identity/maximum copied faults
fail the unchanged equivalence assertion. Evidence and rule/entry matrix:
`implementation/r7-4/manifest.md`. Reused independent reviewer is authorized by
the user after fresh-agent capacity remained blocked. Q-local is corruption
evidence, not timings; full Q-final remains pending. Pause after this checkpoint.

**Expansion refreshed at `fff3136`.** Finite implementation population:
`tests/interfaces/web/_plan_review_scale.py` and its direct
`test_plan_review_scale.py` consumer. Owning docs: PRESENTATION, this register,
CHANGELOG and HANDOFF. Read-only design inspected `884813d`; R7-3 changed neither
validator nor scale tests. Preserve `_validate_children` signature for the
retained R7-2 local evidence checker as well as public validator composition.
Freeze the baseline module, hashes and exact finite corpus before editing under
`implementation/r7-4/`, with its manifest defining artifact conventions.

Use small readiness/measurement receipt helpers only where the same invariant
is checked. Keep boundary-local uniqueness, collection path/order/hash and
partial inspection, readiness completeness and terminal aggregate/membership
checks at their current callers. Compare baseline and candidate public entries
over the corruption corpus below, repairing enclosing hashes to reach semantic
checks. Preserve consumed refusal categories. No new admission rule, producer
dependency, legacy retirement or timing change is authorized. ST-5 requires
same-level corruption detectors; historical E2 is supporting evidence only.
S then I, public-entry equivalence and isolated correctness/identity/maximum
fault detectors, documentation consistency and fresh independent review form
one atomic gate. Q-local has no timed IDs because only validator/test code
changes; full Q-final remains due at R7-G. The regression study maps each old
check to every applicable new entry and proves valid partial evidence remains
inspectable without terminal acceptance. Existing task stops remain binding.

**Objective.** Keep one validator-local implementation of common receipt
invariants without weakening boundary-specific evidence requirements.

**Reduction gate (user clarification).** A shared helper must eliminate a
duplicated rule or state while preserving the independent checks. Record the
before/after rule ownership. If callers retain the same decisions and the helper
only adds another layer to follow, reject that extraction as relocation rather
than simplification. Keep boundary-specific decisions explicit; do not force
them into a generalized helper merely to reduce line count.

**Review and pause (user direction).** If agent slots remain unavailable after
waiting a couple of minutes and retrying, a previous reviewing agent may review
R7-4; a builder may not substitute. That independent reused review counts toward
acceptance. Pause for a recap after R7-4 acceptance; do not start R7-5 implementation.

**Scope and approach.** `_plan_review_scale.py`'s collection/readiness/terminal
entry points and their direct scale tests. Extract small readiness/measurement
receipt checks; keep path/hash/order checks at collection boundaries, uniqueness
at every boundary that currently checks it, and complete membership/aggregate
budgets at terminal acceptance. No producer import/shared oracle, schema change,
legacy retirement, permissive parsing or new generalized validation framework.

**Acceptance criteria.** Baseline and candidate public entries agree over the
declared valid/corrupt corpus. A valid incomplete collection is inspectable but
cannot receive terminal acceptance. Distinct readiness and measurement shapes,
independent expected statistics and all existing identity checks survive.

**Regression watchlist.** A helper may omit a field, coerce Boolean to number,
shift uniqueness to terminal only, or impose completeness during partial
inspection. Error setup must reach the intended check, not fail on an unrelated
outer hash. Preserve externally consumed refusal categories; incidental private
helper wording is not a new public contract.

**Tests and evidence.** S then I and Q. Finite corpus: missing/extra keys; wrong
schema/case/runtime/correctness/sample count or ordinal; Boolean/wrong numeric
type, negative sample or populated inactive field; reused child/launch/process
and headed-plan identities wherever checked; changed bytes/hash, missing receipt,
invalid path/order; incomplete membership; separate P95 and maximum-only failure.
Run each applicable case through partial/readiness/terminal public entry points.
Seed bypasses of correctness, identity reuse and maximum rejection separately;
recompute enclosing hashes for semantic faults. Each mutant must be detected.

**Documentation and handoff.** PRESENTATION records unchanged boundary duties and
independent validator lineage. Retain baseline validator/corpus evidence and Q
artifacts; record any intentional private error-wording changes.

**Adversarial review.** Compare old checks to new call sites, with a check-to-entry
matrix, and verify no producer constant/algorithm supplies the expected answer.

**Commit gate.** All above checks, Q and baseline pass before
`refactor(presentation): Consolidate independent receipt validation`.

### R7-5 — Consolidate receipt publication bookkeeping (A2)

**Objective.** Remove duplicated receipt persistence/accepted-attempt transitions
while retaining truthful interrupted collections.

**Reduction gate (user clarification).** The extracted operation must own the
duplicated publication-to-acceptance transition once. Callers must not retain
parallel decisions or state updates for that same transition. Preserve their
distinct readiness and measurement orchestration and independent validation;
an additional forwarding layer alone does not satisfy this outcome.

**Scope and approach.** `plan_review_benchmark.py`'s `run_readiness`, `run_gate`
and their receipt/index helpers plus direct scale tests. Extract one local
operation for canonical publication, hash and accepted-prefix bookkeeping.
Leave run planning, subprocess freshness, sampling, child checks, watchdogs,
schemas and readiness/measurement orchestration explicit and unchanged.

**Acceptance criteria.** For each collection kind, baseline and candidate agree
on accepted prefix, first unaccepted attempt, receipt bytes and index meaning at
each interruption boundary. Earlier accepted receipts survive, index entries do
not reference unpublished receipts, and incomplete evidence cannot pass terminal
validation. No automatic resume, merge, reuse or overwrite is introduced.

**Regression watchlist.** Mutation before successful atomic publication, stale loop-item
bookkeeping and overbroad cleanup can lie about acceptance or erase evidence.
Before extraction, characterize permitted orphan/staging artifacts at each
boundary; do not invent a stronger cleanup/recovery promise in a test rewrite.
The writer uses byte writing and atomic replacement, not an explicit
flush-to-storage guarantee. This exception/interruption study makes no power-loss
durability claim.

**Tests and evidence.** S then I and Q. For both kinds, inject ordinary exceptions
and relevant `KeyboardInterrupt` at: before publication; after receipt publication
before acceptance bookkeeping; after acceptance before next-index publication;
next-child failure; terminal-output publication failure. Distinguish the last
case: baseline marks a collection complete before terminal output publication.
All children may remain accepted, with no first unaccepted attempt, when only
that output write fails. Preserve that complete collection while withholding
terminal-artifact acceptance; do not invent a failed child or require the
collection to become incomplete. Preserve tests
`test_failed_readiness_preserves_first_accepted_child`,
`test_interruption_after_readiness_receipt_uses_first_unaccepted_attempt` and
`test_failed_measurement_preserves_validated_child_and_rejects_corruption`.
Use semantic failure boundaries rather than fragile Nth-helper-call counts.
Seed acceptance-before-publication, previous-item-as-failed-attempt and deletion
of an accepted receipt. Inspect on-disk evidence with the independent validator;
do not mock the new persistence operation wholesale.

**Documentation and handoff.** PRESENTATION describes the preserved publication
boundary and allowed interrupted artifacts; record the failure matrix and new Q
lineage without claiming resumable collection.

**Adversarial review.** Trace receipt and index state at every fault point and
compare readiness/measurement differences; reject callbacks or mode switches
that hide those distinctions or make the helper larger than its duplicated logic.

**Commit gate.** All above checks, Q and baseline pass before
`refactor(presentation): Consolidate benchmark receipt publication`.

### R7-6 — Share browser admission replay (A4)

**Objective.** Give start/Plan-again and Execute the same bounded admission-retry
algorithm while preserving their command-specific behavior.

**Scope and approach.** `bridge.js`'s `submitStart` and `startExecution` loops;
required Node bridge probes, direct source-anchor/static consumers and optional
trace anchors affected by this extraction. A private helper receives frozen
payload, command, result validator and timeout. Keep logical ID creation outside
the helper and its one automatic-replay allowance inside the logical submission.
No read retry, task-close recovery, app settlement or service admission changes.

**Acceptance criteria.** Lost first reply permits one exact automatic replay;
continued uncertainty yields the existing manual retry operation. Manual retries
retain payload/logical ID and never renew automatic replay. Transport identities
remain fresh. Certain refusals propagate without retries. Existing per-command
validators, Plan-again new-task identity check, timeouts and uncertain-error API
retain baseline behavior. Do not silently harden validators as part of extraction.
Same-task execution is the product contract; existing browser shape validation
does not itself establish rejection of a foreign-task Execute result (F1).

**Regression watchlist.** Recreating a closure can reset the replay allowance;
moving ID creation can duplicate domain effects. A mocked app wrapper may conceal
production Execute regressions. Source-rewriting tracer anchors are direct
consumers even though tracing is optional; repair extraction-caused anchor
breakage in this checkpoint without undertaking R7-8's independent cleanup.

**Tests and evidence.** B then I, H and Q. Extend real production-wrapper probes
behind `test_required_node_start_plan_identity_and_timeout_contract` and
`test_required_node_interactive_wrapper_is_bounded_single_attempt` with Execute
lost-first/lost-both replies, certain refusal on either attempt, repeated manual
retry, exact payload and transport identity assertions. Preserve command-specific
result cases and installed Setup/Plan-again/Execute witnesses. Seed reminted
logical ID and reset automatic-replay allowance; both must fail ordinary probes.

**Documentation and handoff.** BRIDGE mechanism wording and trace-anchor notes if
affected; no protocol change. Record the retry-state matrix, installed evidence
and Q lineage. Preserve any separately reported validation concern as deferred.

**Adversarial review.** Inspect retry closure lifetime and exercise the real
Execute wrapper, including repeated uncertainty and a certain replay failure.

**Commit gate.** All above checks, Q and baseline pass before
`refactor(interfaces): Share bounded admission replay`.

### R7-7 — Avoid unused selection resolver work (A12, narrow outcome)

**Objective.** Avoid deriving folder toggleability when no folder identifier is
resolved, without changing authoritative selection mutation or its final decision.

**Scope and approach.** `service.py::_resolve_plan_selection_ids`: return an
empty result immediately for an empty tuple; derive toggleable membership lazily
once per resolver call only when a node/folder ID needs it. Keep known operation
ID classification, sorting/deduplication and tree validation. Keep workflow
`apply_selection_mutation` and final `derive_execution_selection` untouched.
No public API, shared safety context, retained cache, preview transfer or admission
refactor. This intentionally leaves two authoritative workflow derivations.

**Acceptance criteria.** Empty/direct-ID resolution does no tree construction or
pristine selection derivation. Multiple folder IDs in a call derive membership
once. Effective selections, exclusions, digests, revision/receipt/noop behavior
and refusals equal baseline for the declared cases. An empty resolver result
must not become a whole-command early return. Safety-disabled direct operations
still reach and fail authoritative workflow validation.

**Regression watchlist.** Mixed IDs may need folder filtering after direct-ID
resolution; reselection closes dependencies; unknown IDs must not disappear.
Skipping resolver work must not bypass malformed-ID, stale revision, replay or
blocked/incomplete-scan behavior. Do not make externally supplied safety facts
trusted to avoid calculation.

**Tests and evidence.** M then WI, L, H and Q. Characterize empty tuples, direct,
folder, mixed, duplicate and unknown IDs; blocked correspondence/incomplete scans;
deep dependencies, reselection, noops, stale revisions and replay. Retain
`test_br_g_12_unknown_and_safety_excluded_mutations_are_refused`, both BR-G-24
full-subtree/safety-disabled folder tests, and
`test_br_g_14_revision_conflict_noop_and_digest_cycle_are_distinct`.
Count actual resolver derivations/tree construction through the service path;
keep independent expected membership/reasons/digests. Seed missing safety
filtering, bypassed workflow validation and broken dependency reselection
separately; retained behavioral checks must fail. Counts prove the narrow work
avoidance, not a latency improvement or one derivation per mutation.

**Documentation and handoff.** PRESENTATION/ARCHITECTURE mechanism descriptions
only if needed; explicitly keep the broader A12 proposal deferred. Record Q by
actual measured paths: the depth-32 direct helper is not the full service gesture.

**Adversarial review.** Trace mixed/direct safety-disabled IDs into the unchanged
workflow validator and compare baseline refusal/revision semantics. If preserving
them requires a workflow redesign, stop for adjudication.

**Commit gate.** All above checks, Q and baseline pass before
`perf(interfaces): Avoid unused selection resolver derivation`.

### R7-8 — Replace the mirrored trace oracle (A11, narrow outcome)

**Objective.** Remove the test's duplicate implementation of source transformation
while independently detecting missing instrumentation and failed restoration.

**Scope and approach.** The transformation test in `test_setup_headed.py` and
its narrowly required fixtures. Keep `_plan_again_trace.py` instrumentation,
18 anchors, three assets, four parent/child consumers and diagnostic capability.
Use independently authored observable insertion/anchor expectations and byte/hash
checks; do not calculate expected output with the transformer's replacement table
or a second copy of its regex/newline algorithm. Depends on R7-6's final asset
spelling. No tracer deletion or shared fake DOM framework.

**Acceptance criteria.** Every intended insertion is witnessed independently;
no-op/partial transformations cannot pass via self-consistent hashes. Original
bytes restore exactly on normal exit and exception. Missing/duplicate anchors
refuse before any asset changes. LF/CRLF behavior stays supported. Wrapper
delegate-once, original result/exception and bounded sanitized trace checks stay.

**Regression watchlist.** Hash agreement alone can certify wrongly instrumented
bytes. Assertions imported from the production replacement table share errors.
Overly exact whole-source snapshots can recreate the coupling being removed.
Use a finite per-insertion witness list plus existing delegation and restoration
tests, not a new general instrumentation framework.

**Tests and evidence.** T then I. Seed skipped insertion with updated reported
hash, one corrupted restored byte, missing and duplicated anchors; each must fail
the intended ordinary assertion. Exercise normal/exception exits and both newline
styles. Retain `test_plan_again_trace_anchor_failure_makes_no_partial_mutation`
and delegate-once/rethrow controls. Product, transformer and child drivers stay
unchanged, so H is not required solely for this ordinary-oracle edit; if an
actual headed harness/asset changes, apply H. Record Q's exact dependency decision.

**Documentation and handoff.** TESTS only if verification guidance changes;
retain diagnostic purpose in INTERFACES/PRESENTATION where currently described.
Record removed mirrored logic, independent expectations and mutation evidence.

**Adversarial review.** Reviewer demonstrates why a transformer that returns
unchanged assets, omits one insertion or reports new hashes for wrong bytes
cannot pass. Confirm all four trace consumers remain available.

**Commit gate.** All above checks and baseline, plus any triggered H/Q, pass before
`test(interfaces): Decouple Plan-again trace oracle`.

## Overall final sweep — R7-G

Completion requires every selected row and a separate integrated review. Run O
and L on the final candidate; run H against the final installed product because
R7-3/R7-6/R7-7 affect desktop paths. Earlier identical final-byte evidence may
be reused only with a recorded dependency/identity justification; do not rerun
unchanged gates reflexively or claim intermediate bytes certify later changes.
Run Q-final once for all 35 cases on the final measured bytes and verify committed-source
identity after the final atomic commit. Record all commands, results and skips.

Review one integrated user flow: open fresh Plan review; search/filter/collapse/
sort; direct and folder deselection/reselection; exact stale/replay refusal;
snapshot-bound destructive confirmation; Execute through uncertainty/retry;
truthful admitted/refused state and fresh Plan-again. Preserve current ownership,
request bounds, fresh preflight, receipt and cleanup behavior. Trace test-only
changes through real producer/validator observations and the baseline-to-candidate
fault-detector matrix. Confirm no public constructor/DTO, legacy validator,
tracer or deferred A5/A6/A7/A8/A10 mechanism was silently retired.

Review all regression-map rows and deferred findings; verify active subject docs,
examples and artifact pointers reflect the final behavior without rewriting old
evidence. Quantitative claims must identify measured bytes/profile and cannot
promote E1/E2 or counted witnesses into latency acceptance. Run `git diff --check`,
relative-link checks, and inspect tracked/untracked changes for accidental scope,
temporary data, seeded faults and unrelated work. Preserve retained evidence;
remove only positively identified disposable copies under their checked roots.

A separate adversarial reviewer examines the complete diff and actual evidence,
including surviving mutants, baseline discrepancies, skips and any uncovered
product defects. Every selected outcome must pass without unresolved introduced
regressions. Log/report latent product defects and obtain adjudication for any
blocked gate; never declare the plan complete merely because all ordinary tests
are green. Update M1_PLAN/this register, CHANGELOG and HANDOFF with final closure.
If the sweep needs a separate documentation commit, use
`docs(presentation): Close M1-7 ablation verification`; it must not carry overdue
checkpoint-owned fixes or missing acceptance evidence.

## Deferred findings and review provenance

The candidate register defines all implementation deferrals. A5 requires a
separate service/lifecycle race design; A6 requires individually scoped detector
replacement; A7 must be ratified in ARCHITECTURE/PRESENTATION and M1_PLAN before
internal port design; A8 needs hotspot evidence; A10 requires archival policy;
A11 tracer retirement needs a diagnostic-loss disposition; broader A12 needs
workflow ownership/API review. None is an implied follow-on checkpoint.

**F1 — unproven validation concern, report only.** Direct inspection shows
`bridge.js::validateExecutionAdmission` accepts a shape-valid TaskStart result
without itself comparing its task ID to the submitted task. No supported-path
misrouting or corruption was reproduced. R7-6 preserves existing validator
behavior and must not silently add a new hardening outcome. Retain this lead for
separate bounded investigation; if implementation investigation establishes a
product defect, log/report it under the failure policy above without fixing it.

The former Claude reconciliation table is superseded: useful recommendations,
corrections and exclusions are absorbed into the candidate/checkpoint content.
The original report and usage record remain in `dbeb7a5`. Original read-only
review: one Opus 5 xhigh session `bfd6b79e-d74d-4714-a0cc-38bdafe5b5e2`, resumed
once, zero Claude subagents; total CLI-reported cost $9.483037 including separately
reported auxiliary usage. Raw challenged claims are historical evidence, not
implementation authority. This revision used two bounded read-only Codex probes
and an adversarial plan review; it did not start another Claude session.

Study artifacts remain under ignored `build/m1-7-ablation/`: inventories,
original-state receipt, reviewer prompts/raw responses, E1/E2 plans, exact patches
and six control/ablation/fault logs. E1 had 33 passes before/after and detected a
reversed canonical key; E2 had five before/after and detected a missing maximum
check. They are bounded historical support, not current acceptance. Disposable
experiment copies were removed; frozen P9/legacy artifacts remain untouched.

## Resumption block

- **Current state:** execution authorized 2026-09-17; startup baseline at clean
  `d91871f`, product/tests initially based on `5986c57`. R7-1–R7-4 complete; R7-5–R7-8 and R7-G pending.
  R7-1 unchanged S baseline is 54 passed / 1 historical-artifact skip.
- **Next action:** pause for the user-requested recap after R7-4 acceptance.
  On resumption, refresh the R7-5 read-only expansion against integrated R7-4
  before implementation; its helper must eliminate duplicated transition ownership.
- **Commands:** S/P/B/M/T/I/WI/H/O/L above are established repository invocations;
  Q's supported CLI flags are recorded, but actual new install/artifact paths
  must be frozen before execution. Do not infer a pass from a skipped artifact test.
- **Measurement decision:** Q-local affected Tier 1 checks before each checkpoint
  commit; Q-final full suite once at closeout. Full acceptance remains pending.
  Deferred A7 design is still separate work.
- **Preserve:** current user changes, committed study, original review/E1/E2
  evidence and P9/legacy bytes. New diagnostic files use the checkpoint-specific
  ignored directory and a manifest; no ad hoc files elsewhere or accepted-file
  overwrites. No pushes, PRs or later product checkpoint work is included.
- **Stops:** baseline discrepancy needs classification; a surviving mutant or
  missing required evidence blocks the row. Latent product defects are report-only.
  Apply AGENTS always-stops, recurrence and isolated recovery rules; no silent
  scope expansion, threshold weakening or exemption from a failed gate.
