# Post-M1-8 Ablation Study

## Disposition (2026-09-25)

Original investigation baseline: clean `milestone1` at `549f3b4`. Reconciled
against `a7f8402` and the user's subsequent dispositions. The central diagnosis
is supported; the original deletion sequence and blanket redundancy claims are
not. This document retains the investigation and dispositions; the actionable
plan and sole checkpoint register are in
[M1_PLAN](M1_PLAN.md#post-m1-8-reduction-plan).

S3's server-snapshot direction is accepted. L5/L7/L8/L9 are rejected. D1–D7
are distinguished as settled directions, preferences or unresolved choices in
§11; D2 now removes elapsed-time mutation abandonment/replay while preserving
original-outcome recovery, and D4 is retained without feature reduction.
Recommendations do not silently become user decisions. PA-1–PA-3 in
[M1_PLAN](M1_PLAN.md) authorized the earlier documentation reconciliation and
study retirement only. The user subsequently activated the complete AB batch;
the current register owns status and dependency gates. AB-1 establishes
documentation ownership without demoting an executable measurement gate;
AB-2 owns that atomic transition.
The user's latest W2 instruction replaces the earlier proposed eligibility test;
§8 records the small-change default and user-owned classification.
The old M1-7 execution register is retired,
not resumed or declared fully delivered; §13 accounts for its unfinished work.
The AB-6 prerequisite now has installed gesture evidence: F5/Ctrl+R/Alt+Left
did not navigate, mouse Back traversed same-document fragments, and right click
produced a DOM event without a sampled native popup. The current register owns
the receipt and its limits. The source descriptions below retain the study
baseline and must not be read as current implementation status.

## Question and method

Question: which mechanisms, tests and workflow steps can be removed or merged
while delivering the same user-visible behavior and the same data-safety
invariants? Logical simplification is the goal; line counts are a consequence.

- Outside-in: architecture, behaviors, seams, modules, transactions, then code.
  Nine read-only `claude-sonnet-5` analysts covered disjoint areas (task
  lifecycle/dispatcher, web transport/host, frontend assets, plan-review
  pipeline, core events/history, executor/sync/recorder, scanner through
  inventory, test coupling, measurement/tools) with one classification:
  essential, supporting, defensive-internal, speculative, unintegrated, or
  evidence/process.
- Headline claims were re-verified in code by the orchestrating session; rows
  marked *analyst* were traced by one analyst and not independently re-read.
  Two analyst figures were corrected (the `bridge.js` validator share, and
  per-commit counts that double-counted merge commits).
- Quantitative census from Git, BUGS and the active documents. Experiments ran
  in a disposable local clone of `549f3b4`, with Node v22.18.0 supplied through
  `NAMISYNC_TEST_NODE`. Logs and scripts are retained in ignored
  `build/post-m1-8-ablation-20260925/`.
- Limits: no timing or headed runs, no new product-correctness claim, no
  mutation framework. Line counts are physical lines at `549f3b4` and are
  diagnostics, not promised savings.
- Reconciliation inspected lifecycle, service/port/observer, dispatcher admission
  and event delivery, web drain/review/bridge and shell consumers, history
  readback, review admissions, executor diagnostic consumers, and the five
  earlier studies. The retained experiment logs/scripts were checked, not
  rerun. Source findings below do not establish concurrency equivalence or
  measured refactor savings. The bug census records categories, not causal
  attribution of engineering cost or proof that half the effort was avoidable.

## 1. Findings

The filesystem engine (scan, plan, preflight, execute, verify and ledger) mostly
earns its complexity: nearly every executor guard examined maps to a SEVERE
entry in [BUGS](BUGS.md). The avoidable cost comes from three sources:

1. **Orchestration partly driven by avoidable recovery scenarios.** One
   desktop task spans about 28 named types in six owners. The transport recovers
   from page reloads not exposed by the inspected production configuration, and from deadlines the page imposes
   on its own local calls. Local delivery can nevertheless fail after an effect;
   some identity, result retention and observation recovery remain necessary.
   Interface and dispatcher/history entries are 47% of
   all recorded bugs, and their titles describe the machinery (custody,
   generations, receipts, races) rather than file synchronization.
2. **Repeated internal work needs boundary-specific examination.** ARCHITECTURE
   invariant 17 ("validate once at adoption") already distinguishes immutable
   values from mutable overlays, freshness and capacity. Some repetition is
   avoidable, but storage and ownership-transfer validation earns its place. MOVE-1
   (`549f3b4`) is the precedent: a duplicate check with different evidence
   disagreed with the authoritative one and caused the defect.
3. **Mechanisms recorded as contracts.** Documents state mechanisms and even
   pixel values normatively, acceptance evidence hash-binds about 40 source
   files, and a typical product commit edits five documents. Earlier reduction
   passes therefore had to rewrite the documents that prescribed each mechanism
   before removing it, and removed little.

Three small behavior-preserving refactors broke no behavioral test (§6), while
one broke two visual/source-literal tests. This supports specific coupling
findings, not a general proof that the ordinary suite tolerates all refactors.

## 2. Cost census

| Signal | Measurement at `549f3b4` |
| --- | --- |
| Size | Product: 67.5k Python + 15.2k JS/CSS/HTML. Tests: 182k Python + 16.7k JS (2.7× product Python). Tools: 14k + a 63k-line settlement baseline JSON. Docs: 23k active + 20k obsolete. `build/`: 260 evidence directories, about 11 GB |
| Bug origin (268 BUGS entries) | Interfaces 99 + dispatcher/history 28 = 47%. Scanner, planner, preflight, executor, verifier and database/inventory together 74 = 28% |
| September churn (173 non-merge commits) | Changed lines: docs 48.4k, product 37.7k, tests 71.3k. 49 docs-only commits versus 22 `feat`. Product-touching commits edit 5.2 documents on average (maximum 17) |
| Example | `f6c9471`, a two-line CSS stroke fix, also changed CHANGELOG, DESKTOP_UI, FEATURES, HANDOFF, M1_PLAN and two tests. The `1.2px` value now lives in CSS, a test literal and the feature catalog |
| Documentation register | 211k words in active docs; "exact" 1,108 times, "never" 550 times; about 3,900 code identifiers. "custody" appears in 30 documents, "settlement" in 27, "receipt" in 24 |
| Ordinary suite time | About 4.5 minutes. The slowest tests are the scale/evidence family (about 50 s of the 80 slowest). Maintenance, not runtime, is the cost |

## 3. Behavior-to-mechanism map

| User-visible behavior | What it needs | What exists in addition |
| --- | --- | --- |
| Start a plan or inventory from Setup | Fresh location admission, a task record, session submission, visible state | JS replay/manual retry, a 48-entry adapter response cache, and application effect receipts with a 64-way command guard. Admission/completion delivery has separate acknowledgments. Dispatcher and application rollback own different resources and already connect through an attachment callback; they are not duplicate cleanup implementations (§4 S5). |
| Review a 120,000-row plan | Workflow projection and window, dependency-closed selection, revision guard | `NodeTree` rebuilt on every folder gesture because layering keeps the service from the adapter's projection. Full dependency derivation four times per gesture, two unused. A full O(operations) preview built and discarded on each view open. A second round-trip re-reading membership already returned (*analyst*) |
| Execute with pause/resume/cancel | Commitment digest, preflight, executor guards, progress, control flags | Execution-authority snapshot/revalidate/audit calls at 38 sites in `workflows/sync.py`. Progress attempt semantics enforced in Python and again by a JS reducer. Three envelope encoders/validators |
| Close a task | Cancel when busy, release resources, remove the card | Four-phase settlement claims, a 48-entry close-response cache, and a six-step teardown chain whose steps must each tolerate repetition |
| Survive page reload | No intended explicit user action: production uses `debug=False`; the pinned runtime disables browser accelerator keys/context menus from that flag. Unexpected document replacement still needs containment. Installed gesture characterization is recorded in M1_PLAN's AB-6 prerequisite. | At the study baseline, three generation owners react to `before_load` (`web/host.py`), with native-return and reinjection recovery. Test reload scenarios are real consumers. Ordinary observation recovery is distinct: M1-8 Retry updates must not be removed merely because reload recovery retires. |

## 4. Structural proposals

These are bounded design recommendations. §12 gives the proposed timing.

**S1 — Declare reload unsupported and collapse generation machinery.**
User direction: reload is not intended as an explicit user action. Verify F5,
Ctrl+R, Alt+Left, mouse Back and context-menu behavior in an installed build.
Recommend retiring in-place reinjection/reload recovery while keeping startup
readiness, navigation/origin checks, shutdown fences, and rejection of callbacks
from a retired document. A second document load must revoke command authority
and present a restart path without prematurely releasing a running worker's
resources. It does not cancel an already admitted filesystem operation.
Consolidate generation owners only after mapping these remaining uses; do not
promise deletion of all native-return containment. Ordinary lost-observation
recovery remains separate. Risk: medium at the host boundary, not proven low
by disabling F5 alone. No renderer-crash recovery claim is added.

**S2 — Remove elapsed-time mutation abandonment and replay.** The page applies 5 s and
30 s deadlines to local cross-runtime calls (`assets/bridge.js:55-108`). A deadline turns
a call into "uncertain", which drives automatic replay (`createTask`,
`submitStart`, `startExecution`), the delayed `closeTask` retry loop, the
manual-retry UI and attempt machines in `app.js` (*analyst*), the server replay
caches and the asynchronous completion channel. The M1-async design was framed
around reload survival and a 30 s browser deadline over a 25 s server close
wait. **D2 is settled:** remove page-side elapsed-time deadlines that abandon
mutating command results or automatically replay mutations. Keep delayed-response
feedback, bounded attempts to recover observation, authoritative command identity,
duplicate-effect protection and original-outcome retention/recovery. Keep startup,
shutdown, worker/resource and genuinely bounded observation timeouts. Failed
communication must produce explicit "outcome unavailable" feedback instead of
unqualified "working…" indefinitely; a later valid observation may resolve it.

Native delivery can fail after an effect. Removing reload or arbitrary deadlines
does not remove that uncertain outcome, and delivery cleanup must not erase effect
truth. Recover the original result when available; do not equate unavailable
observation with operation failure, cancellation or permission to repeat mutation.
Retain bounded result lifetimes and existing process-lifetime recovery limits.

The delivered M1-async path already separates admission/completion for several
commands through `CommandSpec`, bridge custody and `DocumentChannel`, with
browser correlation and existing task/session effect receipts. AB-7 simplifies
that path and its direct-command consumers; it does not introduce a parallel
admission/result protocol or redesign the whole command system. Delays may
prompt observation checks without abandoning the original result. Risk: medium;
complete this bounded change before S3 freezes its wire shape. New protocol needs
would require explicit scope adjudication, not follow automatically from D2.

**S3 — Render server snapshots instead of reducing events in the browser.**
Accepted direction; recommended before M1-9 adds an inventory consumer to the
same shell. Refactor the existing task-update seam, not the whole shell.

Current path: `dispatcher/event_bus.py` may report Gap; `session_observer.py`
feeds `web/drain.py::_TaskState`; the drain coalesces Progress and retains
execution outcomes; `assets/bridge.js` reduces event sequencing/progress;
`app.js::acceptTaskUpdate` again interprets task/control/terminal state; and
`task_status.js::advanceProgressPresentation` maintains percentages and rate
samples. Coalescing and retained outcomes are not already a complete server
snapshot reducer. Gap can originate upstream of the web drain: changing the
browser payload alone does not recover missing facts.

Target: one Python owner of task presentation facts, publishing immutable,
task/session-bound revisioned snapshots with terminal/recording axes, progress
and explicit unavailable/incomplete facts. Keep item windows/details bounded;
never ship the complete retained outcome map on each update. Adopt snapshots
atomically, reject stale or foreign identity, and preserve unknown counts after
Gap until authoritative reconciliation exists. An observation retry reads
current state; it does not restart execution. Browser-side drafts, focus,
scroll, pending interaction feedback and purely visual formatting remain local.
Choose one owner for throughput/ETA sampling during design; do not move it to
Python and also keep an authoritative second history in the page.

Use existing rail/panels/review renderers and replace their update input. A
bounded shell refactor is valuable now because `app.js` mixes transport-event
interpretation with controls, follow, window invalidation and close. A general
frontend rewrite, framework adoption, or preparatory file-splitting pass is not
justified. S3 need not wait for S5's application-owner merger. The exact Python
owner/port belongs in the activated design under INTERFACES/BRIDGE, respecting
workflow ownership of sync policy and dispatcher's domain blindness.

Verification must cover real producer-to-snapshot-to-page composition: deferred
directory progress, retries/attempt changes, large integers, Gap/terminal
reconciliation, zero/unrun outcomes, control feedback, navigation, observation
retry and pending Close. Retire only obsolete event-reducer scenarios in the
drain probe, not its whole transport/cleanup coverage. Preserve CLI/history event
contracts. Risk: medium-high; benefit is one fewer semantic interpreter, not
a promised line count or measured speedup.

**S4 — Validate at ingress, at storage and at ownership boundaries.**
Worth doing now only as a narrow consolidation of repeated traversal at the
bridge response boundary (L4), and removal of obsolete browser event semantics
with S3. Do not start a repository-wide validator-removal pass.

| Examined candidate | Requalification and action |
| --- | --- |
| History write/readback, `core/events.py::envelope_from_dict`, `db/history.py::_history_event` | Retain. Persisted JSON is a new adoption boundary, not the original immutable in-memory value. Keep write admission before queue/flush mutation, read decoding/shape checks, column/hash/receipt consistency, append-only protection and current SQL constraints/triggers. The original removal premise was wrong. |
| `web/bridge.py::to_primitive_view`, response snapshot/admission/projection helpers | Confirmed separate graph walks. Consolidate capture, semantic validation and projection where they operate on the same detached value. Keep bounded construction, approved types, canonical scalar/JSON encoding, cycle refusal, longest admitted drain prefix and custody lifetime. A one-pass implementation is a candidate, not a requirement if it complicates safe prefix capture. |
| Browser response validation (`assets/bridge.js`) | S3 can retire event-transition/attempt logic that Python will own. Keep protocol/version, task/session/request/revision identity, scalar decoding and renderable shape checks at browser adoption. Reduce repeated certification after adoption; do not broadly trust every first-party response or remove safe text/layout sinks. |
| `workflows/sync.py` authority checks | Excluded. `ExecutionSetAuthority` snapshots mutable status/recording/publication overlays; transfer and callback audits protect changes across collaborators. The call count does not demonstrate redundant checks. No continuation, settlement, post-copy or callback-audit removal. |
| Plan/preflight validation (L6) | Not qualified for implementation. Constructor shape/capacity, canonical serialization and producer semantic membership may protect different boundaries. Constructing `Verdict(not refusals, ...)` and checking that invariant are not two competing policy owners. Require a specific same-value/same-boundary duplication before proposing removal. |

For each consolidated bridge path, identify the original validator, detached
value and receiving owner. Preserve malformed-input refusal and byte-limit
boundaries with existing response/transport tests and direct consumer checks.
Do not create a generic trusted-value framework or bypass flag. Source inspection
supports bounded L4 work, not equivalence of a new codec. Current history and
workflow safety tests remain mandatory and unchanged in purpose.

**S5 — Reduce duplicated application coordination, not all task ownership.**
The original ten-line proposal understates an architectural change. Defer the
full merger; it is not a prerequisite for S3 and is not worth implementing now.

| Current owner / source | Actual responsibility | Consequence for consolidation |
| --- | --- | --- |
| `TaskLifecycle` in `interfaces/task_lifecycle.py` | Effect receipts, shell/task/session/plan associations, claims excluding observation/mutation/retirement, logical settlement. Own condition plus striped command locks; no calls into physical cleanup. | Much of the state protects real concurrent start/close/follow-up behavior, including headless sessions. Reload removal alone does not remove it. The 64 command locks are stripes, not 64 independent transaction protocols or a handler-admission limit. |
| `NamiSyncService` in `interfaces/service.py` | Selection reviewing/committing/committed state, admission attachment, observer/workflow/dispatcher coordination and retained-review capture before cleanup. | `_settle_session` orders capture, observer release, dispatcher close, detail/plan retirement and logical completion. Keep effects outside lifecycle locks and distinguish session release from task closure. |
| `SessionObserver` | Stream, subscription, callback and thread lifetime. | Callback drain/join cannot safely become work performed while holding a universal task lock. |
| `TaskRegistry` / `_TaskState` in `web/drain.py`, `PlanReviewState` | Adapter task listing, delivery queue/cursor/generation, execution presentation facts, view registry; each task condition and review RLock protect different local facts. | S3 can reduce delivery/event state; a view reference could later live with its task. That does not require merging application effect authority into the adapter. |
| `Dispatcher._AdmissionCleanup` / `submit` | Unpublished session store entry, event hub/stream and the application's supplied rollback callback. | Complementary to service rollback, not a second implementation of it. Keep dispatcher domain-blind and its cleanup retry/custody ownership. |
| Workflow runtime / retained execution review | Domain artifacts, selection decisions and retained result evidence. | A unified interface record must not absorb domain policy or become a second ledger/result authority. |

The real duplication candidates are repeated task/session identity joins,
adapter start-result caching versus application receipt observation, and the
separate task/view lookups. S1/S2/S3 can remove some reasons for those joins.
Afterward consider a single application task association with adapter-local
presentation state keyed by its identity; this is a possible smaller target,
not an approved new object model. Keep headless CLI sessions, task follow-ups
and terminal-review retention explicit. Sharing a workflow-owned review object
is a separate projection/selection proposal (L3/§13), not an automatic S5 benefit.

Why not one lock: current cleanup runs outside the lifecycle condition, while
observers can invoke sinks and drain producers can wait for queue capacity.
Moving those effects under a combined lock risks circular waits and blocks
unrelated operations. One user still has multiple native/worker/observer threads.
No deadlock is claimed to exist today; this is a refactor hazard established by
the current call graph and wait points.

Existing `test_task_lifecycle.py` cases cover concurrent rollback, settlement
versus reobserve, exact-subject retry, close wakeup and plan-retirement versus
mutation. A later S5 design must preserve these outcomes plus CLI admission,
failed publication, task follow-up rollback and retained review after session
release. It must show which claims disappear and why, not merely move all fields
into a larger class. Keep the documented submit-to-start-publication recovery
limitation honest; this study does not fix or broaden that recovery contract.

## 5. Local reductions

Only L1–L4 remain accepted local candidates in the activated AB batch; their
dependent checkpoint rows still govern when each implementation may begin.
Locality does not by itself establish behavior preservation.

| ID | Change | Where | Evidence |
| --- | --- | --- | --- |
| L1 | Delete the unused mapping lookup (`find_mapping`, `get_mapping_snapshot`, `_disqualified_identities`, about 110 lines); it still embeds the stale-alias pattern MOVE-1 removed from planning | `db/repositories.py:1022-1120`, `:1259` | Verified: no production caller |
| L2 | Derive `toggleable` only when a folder id needs resolution | `interfaces/service.py::_resolve_plan_selection_ids` | Experiment B1 and source inspection. Absorbs the unfinished R7-7; its old "deliver now" wording had already been suspended. |
| L3 | Internal revision-bound selection summary/membership transfer instead of full public preview on view open and split membership reads | `service.py`, `task_port.py`, `web/drain.py` | Confirmed full operation-view tuple construction in `_selection_preview_locked`; `open_plan_view` consumes summary fields. Preserve public CLI/API preview, authoritative workflow mutation and atomic revision/membership capture. Absorbs old A7; not a new desktop selection algorithm. |
| L4 | Consolidate bridge response traversal at the same ownership boundary | `web/bridge.py` | Confirmed separate capture/validate/project walks; bounded S4 owns the conditions. One pass is not mandatory. |
| L5 | Merge producer and retained admission objects | `core/review.py` | **Rejected by user.** Independent counter-free populations and cumulative retained charges are different semantics. |
| L6 | Consolidate plan-volume and verdict checks | `core/planning.py`, `core/preflight.py`, planner/preflight | **Unqualified/deferred.** The cited construction, shape and semantic checks do not establish redundant policy; see S4. |
| L7 | Remove default-off copy diagnostics | executor pipeline | **Rejected by user.** Tools CLI, `tools/executor_rig.py` and `tools/seams.py` are actual consumers. Optional developer diagnostics are useful capabilities, not dead product code. |
| L8 | Merge continuation classes and settlement enums | executor runtime | **Rejected by user.** Different recovery facts and legal states; no demonstrated simplification or safety equivalence. |
| L9 | Replace native Advanced Color detection with CSS | web appearance | **Rejected by user.** Keep the mitigation. DESKTOP_UI records that CSS misses SDR WCG; no replacement spike is scheduled. |

The `StoredSessionRecord`/`SessionRecord` split and first-run database-pair
failure cleanup are not current reduction candidates. Limited reachability is
not evidence that failure cleanup is unnecessary.

## 6. Tests

### Experiments

All runs used the same clone environment and the ordinary default selection
(33 headed tests deselected).

| Run | Change | Result |
| --- | --- | --- |
| Baseline | Clean `549f3b4` | 5,403 passed, 5 skipped, 14 failed. All 14 are environmental: 12 `test_tools_gui.py` cases expect a `.venv` inside the checkout, and 2 `test_plan_review_scale.py` cases invoke bare `node` rather than `NAMISYNC_TEST_NODE` |
| A | One trailing comment in 12 product files (Python, JS, CSS) | Pass and failure sets identical to baseline |
| B1 | Lazy `toggleable` derivation (L2) | No new failure |
| B2 | One shared dispatch helper for the four plan-view mutation wrappers in `bridge.js` | No new failure |
| B3 | Combobox stroke as `var(--nami-combobox-trigger-stroke-width, 1.2px)` (identical computed style) | Two new failures in `test_design_tokens.py`: a literal pin on `border: 1.2px solid …`, and the raw-color scanner (`_has_raw_color` is false before, true after): a lexical false positive |

B1–B3 ran together (5,401 passed, 16 failed); both new failures belong to B3 by
their assertions. Of 17 sampled private product names, 15 have no test
reference. A comment breaks no ordinary test, but the plan-review and
execution-UI authority artifacts hash-bind 38–43 product files each (including
`dispatcher.py`, `service.py` and `core/session.py`), so under current evidence
policy the same comment stales their recorded acceptance. That coupling is
procedural, not test-level.

### Recommendations

- **T1 — Remove unjustified visual and source-literal pins.** The most-churned test files
  since 2026-09-01 are this family (*analyst*): `test_frontend_static.py` in 26
  commits, in step with `app.css`'s 26; `test_component_gallery_headed.py` 24;
  `task_shell_probe.mjs` 23; `test_design_tokens.py` 18. Remove exact CSS
  declaration asserts, the 16 source occurrence counts in
  `test_frontend_static.py`, and the 58-literal gallery exact-matrix test. Keep
  security bans (no `innerHTML`, `evaluate_js` or `localStorage`) and a few
  computed-style checks for accessibility invariants such as focus visibility,
  reduced motion and forced colors. Identify the surviving behavioral detector
  before dropping an assertion that also protects semantics or accessibility;
  a source-literal failure alone does not make its whole test disposable.
- **T2 — Retire tests with their mechanisms.** Activated structural changes may shrink
  `test_task_lifecycle.py`, `test_drain.py`, the transport-custody tests, the
  drain and task-shell JavaScript probes and the reload scenarios of headed
  children. An intentionally retired mechanism needs no one-to-one replacement
  detector. Retain observation/close, malformed-boundary and truthful-result
  tests when only reload or event-reduction machinery is retired; S5 is deferred.
- **T3 — Stop procedure-driven test reduction.** The previous refinement closed
  at a diagnostic net +27 lines ([TEST_REFINEMENT](obsolete/TEST_REFINEMENT.md)).
  Approximate corpus shares (*analyst*): 15% headed harness (about 20% of the
  tests in those files need a desktop), 9% scale evidence, 8.5% tests of tools
  and evidence protocols.

For reduction work, red tests can reflect an intentionally removed mechanism,
not a regression; green tests cannot establish the absence of a regression.
Classify each failure against retained behavior and boundaries before changing
the detector. Record why a deleted assertion is obsolete or where its retained
guarantee is observed. Do not preserve a retired mechanism just to keep its test
green, or erase a guarantee just to make the suite pass.

Keep the executor settlement tests and 30-scenario in-code oracle, the
`FailureDetail` construction AST guard, integrity-selection duplicate/unknown-id
rejection, and the security bans.

## 7. Measurement and evidence

- Families (*analyst*): plan-review scale 7.4k lines + 1.3 MB JSON; M1-8
  execution UI/receipt about 3.4k + 0.75 MB; bridge event benchmark 3.5k;
  transport custody 4.3k + 0.15 MB; settlement oracle 8.6k + a 63k-line baseline
  + 2.6k tests; headed children about 10k.
- An estimated 20–30% certifies the evidence itself: readiness passes, partial
  collection indexes, legacy-family replay and per-family authority/identity
  records.
- Policy contributes materially. [DEFENSE §7](DEFENSE.md#7-quantitative-evidence-and-measurement-authority)
  already distinguishes diagnostics and enforced bounds; escalation rules and
  PRESENTATION's specific acceptance procedures create the expensive coupling.
  Relevant dependency changes can re-arm evidence work; not every dataclass
  edit automatically requires every measurement family. The 35 + 13 cases
  include more than latency, so classification must precede demotion.

**E1 — Narrowed recommendation: optional performance benching, required
correctness and containment.** The user favors retaining useful measurement
machinery without an ordinary development pass/fail bar. AB-1 moves methods and
historical results into [PERFORMANCE](PERFORMANCE.md); AB-2 changes executable
acceptance and moves drivers with their consumers. This study does not itself
weaken the current gates.

Plan the migration of measurement drivers, useful fixtures and instrument code
from `tests/` to `tools/`, retaining tests of their correctness under `tests/`.
AB-1 establishes `docs/PERFORMANCE.md` as the methods/results owner and extracts
historical key observations into a table; PRESENTATION retains contracts and
decisions. AB-2 migrates drivers and changes their gating role atomically with
their consumers. Existing raw JSON stays at its current paths. JSON samples and
authority companions preserve numerical results; screenshots, installed wheels,
native logs and failure context are not necessarily embedded. Preserve existing
raw directories; consider a durable external archive for irreplaceable material
before cleanup, not wholesale promotion of ignored build output into Git.

| Class | Proposed treatment |
| --- | --- |
| Filesystem safety, truthful outcomes, complete request/population admission and bounded windows | Required functional/enforced checks. Never substitute favorable timing or sampled memory for a production bound. |
| Known scaling failures | Keep compact counted-work/behavioral regressions at meaningful sizes, permitting equivalent algorithms. No exact private lookup sequence or whole object-graph certificate merely to protect a soft performance target. |
| Plan/execution UI latency and empirical representation memory | Optional benchmark cases with advisory comparison to historical observations/targets. Missing, slow or noisy results do not block ordinary commits or imply product failure. Wrong fixture/endpoint or failed action makes the measurement invalid, not a fast pass. |
| Release resource/leak checks (SH-G-15), security transport custody and executor settlement authority | Outside automatic demotion. They protect different release/correctness claims; any later change needs an explicit consequence decision. Benchmark timeout/job limits remain tool containment, not performance acceptance. |

Retain representative large fixtures, real installed endpoints where relevant,
simple case selection, sample distributions, revision/dirty-state and runtime/
profile provenance. Use one simple entry point over useful existing drivers;
do not build a general platform or require one physically monolithic script.
Keep optional before/after comparisons. A pre-release run is useful, not a new
mandatory ritual replacing the old gate. Exact speed targets remain undecided.

For the demoted performance families, retire separate readiness certification,
accepted-partial-index protocols, per-family acceptance authority and active
legacy-family replay. Keep ordinary driver/setup correctness, partial raw logs
labelled incomplete, and immutable historical artifacts with pinned interpreter
provenance. Do not preserve a fresh-source hash as an automatic requalification
trigger; record it as provenance. Do not erase historical failures or reinterpret
historical passes as current guarantees. Current artifact readers/tests stay
until their consumers are retired together in the implementation checkpoint.

Do not remove every diagnostic under E1: keep copy metrics (L7 rejected).
Plan-again source-rewriting instrumentation has four actual consumers and a
distinct diagnostic value; retain it for now, then assess whether S3's simpler
update path makes it dispensable. Tracer retirement is not bundled into benchmark
demotion. Preserve independent fixture/correctness expectations; a producer's
self-consistent hashes cannot establish that it measured the intended action.

## 8. Development workflow and documentation

Documents currently prescribe mechanisms: FEATURES carries pixel values and
mechanism names, PRESENTATION prescribes evidence mechanisms, and AGENTS adds
closed registers, finite populations, regression studies, recurrence stops,
recovery branches, evidence retention and multi-document updates per commit.
Each mechanism therefore has three to five normative restatements to
renegotiate before it can change.

These dispositions feed AB-1/AB-2. AB-1 makes W2 durable in AGENTS without
changing test authority; AB-2 owns the later driver and gate transition.

**W1 — Distinguish requirements from current implementation.** Keep FEATURES
about user behavior, DEFENSE about consequence/boundaries, and ARCHITECTURE
about ownership and cross-layer contracts. Module docs may still contain real
normative requirements: a publication order or lock/effect boundary can enforce
safety. Label such requirements by the guarantee they protect; describe other
mechanisms as current implementation, not permanent API promises. Do not make
every module document non-normative. Source owns exact fields/constants unless
an independently meaningful contract needs them. Keep one owner per rule and
link consumers to it. Behavior-preserving implementation changes need accurate
owning documentation, not renegotiation of descriptive prose in several places.

**W2 — Default to small changes; the user owns classification.** Accepted user
instruction: default to the small-change workflow unless the user asks otherwise.
Do not replace their judgment with agent-defined eligibility criteria, size
thresholds or an automatic register requirement for every audit-derived fix.

Checks, appropriate tests, adversarial review, accurate owning documentation and
a concise CHANGELOG summary remain mandatory under their existing applicability
rules. Documentation-only changes still use documentation checks. Keep useful
HANDOFF context and substantive BUGS entries under their existing conventions.
Detailed delivery plans, permanent registers and finite-population worksheets
may be omitted unless requested. An internal working plan is not a requirement
to leave another permanent document. This requested multi-checkpoint plan is an
explicit exception, not a template to impose on later small changes.

If delivery crosses architectural ownership, public contracts, safety guarantees,
or multiple independently deliverable outcomes, explain the concrete boundary
and ask the user to escalate/formalize before proceeding across it. The user
decides; file count, broad tests or time spent alone do not trigger escalation.
Existing explicit authorization persists and safety stops remain in force.

M1_PLAN keeps active outcomes, dependencies and unresolved decisions. Condense
completed MOVE-1, GUI-W1/WR1, M1-4–8 and GUI history into compact records linked
to CHANGELOG, Git/evidence and current subject owners. Preserve DOC-2's pending
branch decision and any still-binding guarantee. Retain meaningful failed and
successful evidence without duplicating chronology or test counts in each doc;
do not add a universal evidence manifest or require one log per gate.

**W3 — Retire registers, preserve decisions.** The five older studies are now
archived under `obsolete/`; §13 accounts for completed, absorbed and deferred
items and names the current guarantee owners. Historical completion populations,
stop/resume instructions and frozen test recipes are not future execution
authority. Historical evidence remains intact; archiving documents does not
retire validators or measurements. Old task-specific exclusions are not perpetual
mechanism freezes, but substantive safety/product decisions need a current
owner and explicit supersession before they can change.

**W4 — Prune duplicated procedure in AGENTS, not its useful constraints.**
Recommend retaining structure/naming, Windows execution, layering, safety and
data preservation, scope authorization, meaningful verification, commit rules
and recovery for actual interruption. Route detailed component/evidence rules
to their owners and apply W2's user-owned small-change default. Keep explicit stops
for supported data loss, unauthorized/duplicate effects and false success.
Do not use this pass to remove recurrence stops, weaken preservation or introduce
a replacement process framework. Draft the actual AGENTS diff when W1/W2/E1
are activated; "reduce it to three topics" is rejected as too broad.

## 9. Retain

These look reducible but protect real behavior:

- Executor final-touch guards, recorder flush before destructive guards,
  publication observation and `canceled-after-publish`/`canceled-after-mutation`,
  UPDATE `live_stat` retention across retries and trash parent-chain
  revalidation; each maps to a SEVERE BUGS entry.
- Preflight's distinct root, subject, temporary and trash probes, and the
  scanner's before/after root bracket.
- The cross-process volume mutex and worker-generation custody.
- The history receipt/prefix hash chain, and `Scalar64`/`FileIndex128`
  handling.
- The complete-request bound and command allowlist, CSP, navigation blocking and
  the filesystem-label layout-control sink.
- Two SQLite files, and the four plan-review admission axes (dependency fan-out
  is not proportional to rows).

## 10. Feature classification

| Class | Items |
| --- | --- |
| Features to keep (simplify their mechanisms) | Plan review with search, filters, sort, selection and highlight ranges; commit-bound execution; pause/resume/cancel; live and retained execution review; Plan again; serial batch pair creation; recent locations; CLI integrity baseline/verify/rebaseline; history CLI; concurrent tasks on disjoint volumes |
| Implemented, not yet integrated (expected) | `tree.js`, `integrity.js`, gallery-only chip/badge/banner CSS, inventory acknowledge/restore (no CLI or desktop surface), desktop inventory projection contracts |
| Future seams, not deletion authority | `SessionStore` record split, destination-policy seam for ingest, recorder `flush()` batching seam |
| Developer diagnostic capability to retain | Copy-pipeline metrics, consumed by tools; Plan-again tracer pending a separate post-S3 usefulness assessment |
| Dead | The mapping lookup in `db/repositories.py` (L1) |
| No intended explicit production user action | Page reload/reinjection recovery (S1); unexpected document replacement still needs containment |

## 11. D1–D7 dispositions

| ID | User disposition and current recommendation |
| --- | --- |
| D1 | Reload probably will not be exposed. Adopt that design direction; S1 recommends retiring recovery after installed verification while keeping stale-document containment. It does not automatically approve all of S2. |
| D2 | **Settled.** Remove page-side elapsed-time mutation-result abandonment and replay triggered by those deadlines. Keep delay feedback, bounded observation recovery, command identity/duplicate protection and original-result retention/recovery, including failure after an effect. Show explicit outcome unavailability when communication fails; retain lifecycle/resource and genuinely bounded observation timeouts. Simplify existing asynchronous admission/completion, not a new command protocol. |
| D3 | No chosen speed targets. User favors optional useful performance benching. E1 demotes the performance families without inventing new targets; enforced bounds and separate release/correctness gates remain distinct. Exact case selection is not yet decided. |
| D4 | **Settled: retain without feature reduction.** Keep row highlighting/focus, range/navigation behavior and their separation from execution checkboxes. This reduction plan does not remove or diminish that capability. |
| D5 | Keep the native Advanced Color mitigation. L9 rejected; no CSS replacement work. |
| D6 | Keep the expected inventory acknowledgement/restore capability. M1-10 explicitly owns baseline/verify/rebaseline and post-copy verification; its rebaseline acknowledgement is different from hiding/restoring missing rows. Service methods and FEATURES already support the latter intent. Allocate its desktop delivery explicitly when M1-9/10 activates; do not shelve it as dead code or claim M1-10 already names it. |
| D7 | User considers §7 excessive. Plan optional performance tooling and a central PERFORMANCE methods/results owner, retaining correctness, enforced bounds and distinct safety/release gates. W2 is now explicitly the user's small-change default with user-owned classification. Durable policy edits are AB-1/AB-2; this planning revision does not demote executable gates. |

Separate settled decisions: S3's direction is accepted; L5/L7/L8/L9 are rejected.
S4 is now restricted to boundary-preserving consolidation. Full S5 is deferred
on the investigation's recommendation; no full task-owner merger is scheduled.

## 12. Planned delivery

[M1_PLAN](M1_PLAN.md#post-m1-8-reduction-plan) owns AB-1–AB-10, dependencies,
regression mapping, acceptance, commit gates and resumption. Documentation is
first; benchmark migration follows its ownership rules. Independent database,
selection, response-boundary and test reductions get coherent commits. S1/S2
and S3 remain separate boundaries; settled D2 makes AB-7 a bounded simplification
of existing admission/completion, completed before S3. Genuine delivery uncertainty
and original-outcome recovery remain. D4 stays intact.
S5 stays deferred. L5/L7/L8/L9 remain in the compact rejected table in §5.
§14 reviews delivered AB-7 and proposes a follow-up; it is not yet a decision.

## 13. Earlier studies: absorption and archival accounting

All five source documents were inspected for status, exclusions, losses and
remaining decisions before moving. Their original bodies are preserved except
for relocation of links and a retirement banner. This section is the current
disposition map; archived instructions cannot restart their old checkpoints.

| Archived study | Open work and still-relevant decisions |
| --- | --- |
| [TEST_ABLATION](obsolete/TEST_ABLATION.md) | TA-1–TA-3 and rebase closed; diagnostic recommendations are not outstanding implementation. Whole-cohort deletion lost duplicate-selection and visual/accessibility detectors. Keep boundary/selection/lifetime/native guarantees under CORE, TESTS, DESKTOP_UI, INTERFACES and DEFENSE. Later PR-8 superseded its exact-frozenset/private-index prescriptions; do not resurrect them. |
| [TEST_REFINEMENT](obsolete/TEST_REFINEMENT.md) | ST-H/ST-0–ST-6 complete. Preserve FailureDetail lifetime/AST scope guards (CORE), database snapshot/bounded-query behavior (DATABASE), duplicate/unknown-id selection refusal and detached facts (VERIFIER/ARCHITECTURE), accessibility and real native input/privacy/media checks (DESKTOP_UI/INTERFACES/BRIDGE). Same-level detection applies to retained guarantees, not intentionally retired mechanisms. MOVE-1 superseded historical-alias query assertions; PR-8 superseded exact selection-container prescriptions. Frozen protected-input lists and mutation scripts are historical receipts, not an eternal file freeze. |
| [PRODUCTION_REDUCTION](obsolete/PRODUCTION_REDUCTION.md) | PR-0–PR-9 complete. HISTORY/DATABASE own write/read validation, append-only receipt integrity and coordinated old/mixed-pair refusal without automatic deletion/migration. ARCHITECTURE/WORKFLOWS own required finishing and independent terminal axes. DATABASE owns bounded batching/snapshot/atomic-write guarantees; exact query-count pins were retired. Execution/integrity continuation protection and unintegrated presentation features remain. Its exclusions authorize no generic lifecycle/settlement/serializer engine; S3 is a new accepted direction, not a claim that this old pass allowed it. |
| [REDUCTION_FOLLOWUP](obsolete/REDUCTION_FOLLOWUP.md) | NR-0–NR-9 complete, no pending delivery. ARCHITECTURE's adoption rule preserves constructor/ingress validation, supported callback changes, capacity/freshness and mutable ownership transfers. HISTORY retains write admission before pending mutation and read normalization/hash/column checks. EXECUTOR retains exact mutation/publication/recording ordering and settlement oracle. Recording-tail, pause/cancel and mutation-verdict compression remain unscheduled; this review does not revive them. |
| [M1_7_ABLATION_STUDY](obsolete/M1_7_ABLATION_STUDY.md) | R7-1–R7-4 delivered; RI-1–RI-4 investigation complete. R7-5–R7-8/R7-G were suspended, not completed. Retire that denominator and resume block; selected ideas are accounted below. Historical P9 evidence and current acceptance owners remain unchanged by archival. |

### M1-7 items absorbed or explicitly left out

| Old item | Current disposition |
| --- | --- |
| Option A readiness/partial-index/legacy retirement | Absorb into E1 for demoted performance families, with failure logs and historical bytes/provenance retained. No new journal or partial-publication protocol. |
| Option B replacement protected acceptance system | Do not build it for demoted optional benchmarks. It was recommended under unchanged hard SLOs, which is not the current proposed direction. Preserve its useful distinction between observations and independently authored correctness expectations. |
| Option C numeric contract rationalization | Absorb into D3/E1: no new hard targets now; retain useful measurements while dropping their proposed automatic gating role. Release-resource decisions remain separate. |
| R7-5 publication helper; R7-8 tracer-oracle rewrite | Supersede the old checkpoints, not their outcomes as "passed". Do not polish partial-index machinery proposed for retirement. The tracer remains for now; any touched instrumentation must still prove actual insertion/restoration independently rather than mirror its replacement algorithm. |
| R7-6 / A4 shared replay helper | Retire the old standalone checkpoint. Settled D2 removes elapsed-time mutation replay through AB-7's existing admission/completion path; do not first build a shared replay framework. Keep authoritative identity, duplicate protection and bounded recovery of the original outcome after genuine delivery failure. |
| R7-7 / A12 lazy resolver | Absorb into L2. Broader cross-call safety derivation/cache reuse is deferred; no bypass flag or trusted context framework. |
| A5 shared selection admission | Defer with S5. Task and general/CLI wrappers have different replay, revision and verification semantics; external work remains outside locks. No callback-heavy admission framework. |
| A6 scenario-local receipts, disconnected checkbox and driver spelling | M1-8 R1 already adopted functional consolidation. Current follow-ups belong to T1/T2 only after rechecking surviving scenarios; do not rerun the old list or build a universal fake DOM. Retain actual stale-response, captured-intent and native input/focus witnesses. |
| A7 internal selection snapshot | Absorb into L3 with public preview compatibility, exact artifact/revision and workflow-owned selection. No workflow graph serialized to the page. |
| A8 stable topology plus selection overlay | Defer: source identifies repeated row/map allocation but no measured material hotspot or demonstrated simpler model. Existing compact order/visibility reuse stays. S3 does not require a projection redesign. |
| A10 legacy interpretation | Absorb into E1 archival treatment when its active readers retire. This document move alone does not delete any historical validator or evidence artifact. |
| A11 optional Plan-again trace retirement | Defer until S3 usefulness review; four consumers make it an actual capability. Copy diagnostics explicitly remain. |
| F1 Execute response/task identity lead | Retain as an unproven boundary concern for S3/S4 response adoption: ensure returned task/session identity matches the requested operation. No supported misrouting was reproduced; no new defect or fix is claimed. |
| R7-G old integrated closeout | Retired with the suspended implementation plan, not marked passed. Each newly activated outcome gets current affected verification under the then-operative policy; historical R7 partial evidence cannot certify a future refactor. |

The archive does not create a second current guarantee catalog: the named subject
documents govern. When a proposal above changes a retained mechanism or evidence
obligation, update that owner during activation. No other open delivery row was
found in the four completed studies; their deferred alternatives remain ideas,
not latent authorization or mandatory future work.

## 14. AB-7 follow-up review: original-outcome recovery (2026-09-26)

User-requested read-only review of delivered AB-7 (`6287db0c`, base `2b4a2214`):
is anything redundant, including original-outcome recovery itself? Method: the
diff, current source, the retained AB-7 evidence under
`build/post-m1-8-ablation-20260925/` and the study's own tiering follow-up.
That initial review ran no tests or experiments; line counts are diagnostics.
Its original proposals are retained below with a later validation/disposition
table. M1_PLAN owns the subsequently authorized AB-7R checkpoint.

### Original findings (qualified below)

AB-7 was a logical simplification that grew product source by about 936 lines
(+1,308/−372: `app.js` +463, `bridge.js` +230, `bridge.py` +157). Most of the
growth is one mechanism: each observed command's response is retained in
native custody until the page releases it, a new `observe:<request_id>:<command>`
message reports `pending`/`ready`/`unavailable`, `bridge.js` adds an observed-
attempt path (11 functions, about 275 lines), and `app.js`/`theme.js` add
per-surface outcome retry/unknown state and cross-surface fences.

| ID | Finding | Evidence |
| --- | --- | --- |
| F1 | Three records of a command outcome now exist: `TaskLifecycle` start and plan-mutation receipts, the drain's 48-entry start-response cache and the new native-custody response. The page mints a fresh `command_id` at all eight sites, every mutating command policy became `retry=NONE`, and Retry only observes. The receipt/cache replay hit paths are therefore reachable only from tests. D2 asked for one authoritative record. | `service.py` `command_guard`/`replay_start` callers; `task_lifecycle.py` `replay_start`; `commands.py` policy table; `bridge.js` `mintId()` sites |
| F2 | Observation counts `pending` as exhaustion. After 5 s feedback and three polls (+0/+100/+350 ms), a healthy running command becomes "outcome unavailable" at about 5.4 s; a later original result is stored but does not update the screen until the user presses Retry. A busy Close can legitimately wait up to 25 s server-side. Pre-AB-7 mutating starts had a 30 s deadline, so slow commands now reach an unavailable state sooner. The behavior is pinned as intended. | `bridge.js` `recoverObservedResult`, `acceptObservedResponse`; `tests/assets/bridge_timeout_probe.mjs:553-579` |
| F3 | "Fixed unknown" and its fences follow from recovering from the transport record: after a post-effect internal error the retained record is the error itself. A domain receipt can answer whether the start committed. The documented gap between `Dispatcher.submit` return and start publication still needs one narrow guard. | `taskCloseBlockReason` (seven outcome flags); `canCancelAfterFixedReviewOutcome` (20 conditions) |
| F4 | Observation also covers commands with no effect to recover (view, highlight, location admission) and commands without `command_id` whose results are visible in drain state or revisioned reads (execution control, Close, release, cosmetic replacement). | `commands.py` `MUTATION_OBSERVED` rows; BRIDGE command table |
| F5 | Observation was layered on the existing asynchronous completion channel, so it reconciles response tokens, completion tokens, early completions and generations. S2's alternative (return after admission; long waits such as Close become task state) was not taken, which is where both `pending` and the double token bookkeeping come from. | `bridge.js` `acceptObservedObservation` |
| F6 | No real lost delivery was observed. Every delivery-failure case in AB-7 evidence is fixture-injected. The one real anomaly (a Setup start normalized to `internal_error`) is a product exception that observation cannot resolve. No captured receipt text links the unexplained Plan-again timeouts to this path. | `ab7-verification.md`, `ab7-installed-failures-readonly.md`; receipt text search |

Verdict: the requirement (after lost delivery, do not repeat the effect and let
the user learn the outcome) remains valid. Safety never depended on transport
recovery: duplicate protection is domain-owned (receipts, commitment freeze,
one session per task, task/session-keyed close). Retaining and observing
transport responses is the redundant mechanism; it duplicates records that
already exist and has made them unreachable.

### Original recommendation

Make the domain record the single outcome authority and retire transport
response retention:

- Retry is a user-initiated resend of the identical command (same `command_id`
  and intent). The owner replays its receipt or, while the original still runs,
  waits for it under the existing equal-id lock. No automatic resubmission, so
  D2 holds.
- No page deadline on mutating results: keep the 5 s delayed/still-working
  feedback with a check action; `pending` is never failure.
- Commands without `command_id`: resend Close and release (idempotent by
  task/session); re-read authoritative state for control, view, highlight and
  cosmetic commands.
- Remove the `observe:` message, retained responses, the observed-attempt path
  and most per-surface unknown/fence state. Keep one narrow unknown-outcome
  message for the submit-to-publication gap, without automatic resend.
- Later, separately: S2 proper (Close returns "closing"; completion through the
  drain) could remove most long-running commands and possibly the asynchronous
  completion channel.

Second-ranked alternative: keep AB-7 observation, delete the unreachable domain
replay-hit paths and stop treating `pending` as exhaustion. It retains the
weaker record: document-bound, and unable to establish an effect after errors.

### Original tiering proposal

Tiering is sensible when it is data, not code. Classify commands by the kind of
effect, not by perceived value; that yields two recovery actions:

| Commands | Effect | Recovery action | Duplicate guard |
| --- | --- | --- | --- |
| `create_task`, `start_plan`, `start_inventory`, `plan_again`, `start_execution`, selection mutations | Keyed by `command_id` | Resend the identical command | Domain receipts; in-flight resend waits for the original |
| `close_task`, `release_terminal_session`, `control_execution` | Idempotent per task/session | Resend, or let the drain show settlement | Lifecycle settlement and close receipts |
| View, highlight, theme/cosmetic, `admit_location`, `pick_folder` | None to recover, or revision-guarded | Re-read current state (or choose again) | Revisions |

The middle tier merges into resend; observing settlement also works but adds a
second mechanism. Value ranking only decides presentation polish, because a
wrong low-tier answer costs clarity, not data. The pre-AB-7 `CommandRetry`
policy column already expressed this tiering; its defect was the timer-driven
automatic trigger. A declared per-command recovery action with a user trigger
keeps D2's intent without transport retention.

Rules that keep the removed complexity out:

- No timer decides an outcome; timers only change feedback text.
- One uncertainty state per pending command, owned by the issuing surface:
  working, delayed, or retry available. No per-surface unknown flags.
- No page-side cross-surface fences; the domain refuses conflicting actions
  and the page shows that refusal.
- The submit-to-publication gap is one message, not a fence system.

Net effect: one table column and one generic recovery call (tens of lines)
against the removal of the observation channel, retained responses, most of the
observed-attempt path and most per-surface outcome state.

### Before adoption (original proposal)

Confirm by test, not only by reading: identical resend returns the original
outcome without a second effect for each keyed command (BRIDGE's replay rule);
waiting on the equal-id lock holds one of the 64 bounded handler slots; and a
second `start_execution` after committed admission returns an existing
disposition (`in-flight`, `frozen` or `conflict`) rather than a new session.
Decide this before AB-8 freezes its snapshot shape, which currently preserves
AB-7's outcome-unavailable and original-result states. Status: proposal
awaiting validation at the time of that review. The qualified disposition below
supersedes this proposed adoption path.

### Validation and AB-7R disposition

The follow-up checked the delivered diff, receipt and retirement owners, adapter
revision checks, native custody and all browser issuing surfaces. Six focused
transport/service/lifecycle cases passed; raw results are
`ab7-study-validation.xml` and `ab7-study-retirement.xml` in the existing evidence
directory. This validates specific seams, not a universal resend protocol.

| Finding | Validated disposition |
| --- | --- |
| F1 | The +936 net product lines and stock browser's fresh-ID/observe-only behavior are confirmed. The three records are not interchangeable: drain start responses coordinate production Close; selection receipts retain intent and return a current projection; retirement removes replay authority. The claim that their usefulness is test-only, and hence that all transport retention is redundant, is rejected. |
| F2 | Confirmed: three healthy pending observations were converted to unavailable and late completion awaited Retry. The cited 25 s bound belongs to event draining, not Close. Keep the original promise pending; qualify failed communication separately and automatically adopt a valid late result. |
| F3 | A fixed error cannot establish the effect, but a domain receipt does not universally answer it either: execution no-effect dispositions lack a permanent start receipt, selection replay is not original-result replay, and an unknown child can retire before resend. Retain effect-critical unknown fences and observation rather than introducing a second recovery protocol. |
| F4 | View/highlight/location are effects: highlight feeds bulk-selection scope and location admission allocates bounded slots. Their recovery can nevertheless be reduced through current revisioned state or deliberate folder rechoice, with stale-response suppression. Close/release/control cannot be treated as freely repeatable across intervening lifecycle actions. |
| F5 | Observation adds reconciliation over existing admission/completion, but response/completion tokens and early-completion handling predate AB-7. Removing them or redesigning Close is not part of this reduction. |
| F6 | The retained evidence has injected delivery loss, not an observed natural loss. The real Setup error and unexplained Plan-again timeouts remain unresolved observations. This does not establish that local delivery cannot fail or authorize unrelated fixes. |

The user authorized the qualified reduction as **AB-7R**, a separate checkpoint
before AB-8. [M1_PLAN](M1_PLAN.md#ab-7r--reduce-command-recovery-and-uncertainty-state)
owns its finite register and verification. Five commands (`pick_folder`,
`admit_location`, `update_plan_view`, `mutate_plan_highlight`,
`replace_cosmetic_section`) stop retaining/observing original responses. Their
current-state refresh or fresh choice does not claim the earlier effect settled.
Eleven effect/lifecycle commands retain original observation and domain duplicate
protection. Bounded Check updates feedback while the original promise remains the
sole adopter; remove the separate reject/retry/adopt branch. No automatic replay,
generic resend, new receipt owner, protocol redesign or D4 reduction is accepted.
Keep actual selection→Execute, start/Close and receipt-retirement dependencies;
remove unrelated presentation/folder fences. AB-8 remains paused.

## Evidence

`build/post-m1-8-ablation-20260925/` (ignored) retains `run-base.log`,
`run-A.log`, `run-B.log`, the earlier Node-less `run-no-node-durations.log`
(durations source), and `scripts/` with the census and experiment scripts:
`sizes.ps1`, `churn.ps1`, `doctax2.ps1` (merges excluded), `bugs.ps1`,
`docpin.ps1`, `refs.ps1`, `prepA.ps1`, `prepB.ps1` and `run3.ps1`. The disposable
clone and its worktrees were deleted after the runs.

Reconciliation checks at `a7f8402`: `reconciliation-checks.json` records the
changed-document link/anchor scan, diff check, unchanged product/test/tool and
AGENTS/DEFENSE paths, and comparison proving that all five archived bodies are
preserved except banners and relocated links. Final adversarial self-review
checked that proposals were not promoted to user decisions (D2/D4 were then open),
that S3 preserves unknown/Gap and bounded-result behavior, that S4 retains
storage and mutable-ownership checks, and that S5 does not collapse complementary
cleanup owners. It also found and removed stale R7-resumption wording from
M1_PLAN. No independent agent review, fresh test run or measured benefit is claimed.

Subsequent plan revision based on `0c74ee7` records the user's explicit D2/D4 decisions.
BRIDGE's existing small asynchronous command contract and current command-policy
consumers were inspected: admission/completion and post-effect delivery failure
already exist. AB-7 therefore reuses that machinery, preserves bounded observation
and unavailable outcomes, and does not promise that all uncertainty disappears.
