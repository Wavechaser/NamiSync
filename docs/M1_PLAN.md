# M1 Delivery Register

This is the sole active M1 delivery register. It records remaining accepted outcomes, their order, and the verification that closes each one. Implemented contracts are owned by their active subject documents; completed delivery history and superseded mechanisms are in [obsolete](obsolete/). The archived plan files retain historical staging and review but are not instructions for new work.

[BRIDGE.md](BRIDGE.md) owns external command, transport, retry/recovery, and bridge-gate contracts. [PRESENTATION.md](PRESENTATION.md) owns trees, views, search, selection, sorting, and scale evidence. [INTERFACES.md](INTERFACES.md) owns implemented task lifecycle and desktop host/package rules. [FEATURES.md](FEATURES.md), [ARCHITECTURE.md](ARCHITECTURE.md), and [DEFENSE.md](DEFENSE.md) remain the owners of product behavior, cross-layer meaning, and safety/evidence policy.

[PRODUCTION_REDUCTION.md](PRODUCTION_REDUCTION.md) is the closed maintenance
subregister for the completed production-ablation pass under M1-12. Its PR-0
through PR-9 rows remove redundant implementation and test prescriptions; they
do not add, defer, or reinterpret an M1 product outcome.

## Main objectives and current boundary

[REDUCTION_FOLLOWUP.md](REDUCTION_FOLLOWUP.md) owns the accepted narrow
immutable-value, scan-validation, history encoding/projection, and executor
simplification follow-up under M1-12. Its NR-0–NR-9 register and migrated RF-E/RF-X
dispositions preserve existing product outcomes; implementation and integrated
verification are complete. Further product simplification is outside the
remaining frontend delivery scope.

The secured desktop host and transport, presentation foundation, current service/CLI surface, and implemented ledger/history boundary are active. The frozen v1 event-and-transport custody claim remains closed at its bridge evidence owner. That closure does not establish whole-runtime containment.

The process-live desktop task shell, shared location admission and frozen Setup
are active, including plan/inventory starts and Plan again. Finish reviewed
execution, execution/inventory projections, integrity controls and first manual
post-copy verification, then release closure. These remain unrealized frontend outcomes. The history page, global-settings mutation
page, drag-and-drop, file-scoped planning, durable task survival across a process
restart, durable sort preferences, status/progress or global-flat sorting, and
compare-and-accept rebaseline semantics remain deferred. User-facing terminal
execution/verification retries (including Verify remaining), user-invoked session
cleanup/trash purge, and richer I/O error categories are deferred to M2; see the
feature-only [M2 proposal](M2_PROPOSAL.md). Existing automatic retries, owned-temp
recovery, transport replay, close/shutdown recovery, and live pause/resume are
not removed by those deferrals.

The prior aggregate complete-owner-graph model and BR-G-45 are retired. No future work inherits its reservation, DTO, lease, byte-budget, command-count, or representation recipe. Completed M1-4 replaced the former task lifecycle/retention preservation checkpoint. Existing externally enforced ingress and population bounds remain active independently.

## Remaining checkpoints

### Completed GUI and documentation work

Completed records are condensed here; CHANGELOG and Git history through
`7e94598` retain individual deliveries, studies, verification and exact diffs.
Active behavior belongs to the linked subject owners, not old implementation
populations or repeated test counts.

| Closed IDs | Delivered result / owner |
| --- | --- |
| GUI-1, GUI-S1–S3 | Task navigation, frozen Setup controls and Settings/About shell; independent rail/work scrolling and preserved task drafts. [DESKTOP_UI](DESKTOP_UI.md). |
| GUI-S4–S12, GUI-R1–R2 | Origin-owned batch receipts, queued removal and settled-result clearing; compact tables with stable header/body gutters; native CSS scrollbar approximation; explicit smoke-only Ready witness; Fluent control and Setup refinements. [DESKTOP_UI](DESKTOP_UI.md). |
| GUI-S13–S21 | Translucent Fluent control fills and authored 1.2px boundaries; keyboard/pointer textbox focus; pinned checkbox glyph; per-pair frozen options; sync-only batch projection. Keyboard, forced-color, exact retry and admission guarantees remain. [DESKTOP_UI](DESKTOP_UI.md). |
| GUI-I1–I3 | Pinned local Fluent icon catalog, provenance, offline generation/checking and maintenance workflow. [TOOLS](TOOLS.md). |
| GUI-D1–D7 | Shadow/disabled-label diagnostics and batch-housing study; M2 records for native overlay scrollbars, verify-only batching and persistent presets. [BUGS](BUGS.md#desktop-material-composition), [DESKTOP_UI](DESKTOP_UI.md), [M2_PROPOSAL](M2_PROPOSAL.md). |
| AI-1–AI-2 | Execution/containment guidance and instruction condensation; component rules routed to their owners. AGENTS remains execution authority; personal-skill edits are separately recorded in CHANGELOG. |
| DOC-1, DOC-3 | Accepted frontend/M2 decisions reconciled across subject docs; completed history condensed and checkpoint expansion procedure established. Documentation verification did not claim product acceptance. |

No rendering fix was established for the WCG shadow halo or intermittent
disabled-label blur. Mica remains required; no workaround or compositor-health
release gate was added. BUGS and DESKTOP_UI retain investigation boundaries and
reopen evidence. Recent availability remains observation, never admission.
The existing 48-pair bound, serial best effort, per-row options and exact
uncertain retry remain active; clearing receipts does not close tasks.

DOC-2 remains **pending, outside this M1-7 task**: the historical branch
reconciliation proposal was to remove exactly four superseded compact-plan
commits from `milestone1`, preserve the old tip and open a draft PR from
`milestone1-anthony`. It requires fresh divergence/remote-tip and work-preservation
verification before action; unexpected commits or unaccounted work require
adjudication. This condensation neither executes nor marks that proposal done.

### Product delivery register

Each checkpoint is a closed register row. A new finding does not enlarge a row; apply the repository containment rules in `AGENTS.md`. A change begins only after its row has named the relevant active subject contracts and finite verification. The row's verification is in addition to ordinary affected department and consumer checks.

| ID | Accepted outcome | Dependencies and named verification | Status |
| --- | --- | --- | --- |
| M1-4 | Process-live blank task creation, navigation and explicit closure through existing lifecycle owners, with generation-aware callback containment. | Delivered in `ab453e1`; ordinary/headed checks and adversarial review passed. Active contracts are in BRIDGE and INTERFACES; concise delivery record below. | Complete |
| M1-async | Separate bounded command admission from asynchronous completion for create/start/release/close, reusing current task/session effect owners and one shared exchange budget. | After M1-4; default before M1-5, permitted after M1-5 but before M1-6. M1-async-G passed; delivered/excluded outcomes and evidence are below. | Complete |
| M1-5 | Give Setup and inventory one workflow-owned location-candidate pipeline with typed admission results and bounded remembered locations. | After M1-4, normally after M1-async. Verify parser refusals; leaf/reparse/placeholder and long paths; missing, offline, remount, and clone ambiguity; bounded recents; activation/slot races and purpose mismatch. Review path parsing and TOCTOU. Scanner, preflight, executor, and verifier retain fresh re-probes. | Complete |
| M1-6 | Deliver frozen, backend-canonical Setup, typed/picker/recent inputs, standalone inventory creation, serial best-effort pair creation, and explicit Plan-again after fresh reviewed-identity resolution. | Verify bounded inputs, canonical snapshots, immediate invalidation, no global-default mutation or browser filter normalization, partial-pair refusal, mixed batches, replay/recovery, slot/plan-generation races, and headed hostile-text/picker/recent flows. Map needed command behavior in BRIDGE when this activates; do not prescribe the retired 18-command expansion. | Complete |
| M1-7 | Deliver bounded plan review, selection, execution admission, and the full plan consumer for sibling sorting. A review remains truthful when execution never ran; an admitted attempt keeps its selection committed. | Exercise plan publication, selection and commitment freshness, stale/replayed mutation, admission-failure rollback versus post-admission preflight refusal, fresh Plan-again review after source/target changes, destructive confirmation, controls, windows/anchors/search/filter, and headed production flows. No terminal selection reopening or subset retry. BRIDGE and PRESENTATION define protocol and projection criteria. | Measurements complete; 12 criteria failures |
| M1-8-capacity | Distinguish recognized disk-capacity I/O failure and stop admission of later executor operations after settling the current operation. | Before M1-8, use the existing failure-policy/Stop and settlement paths; verify direct and wrapped capacity failures, ordinary I/O distinction, current-effect/recording truth, later work left unrun, terminal projection, and unchanged sharing-violation retries. Run executor plus core/workflow/interface consumers and the retained settlement oracle. No general I/O taxonomy or settlement restructuring. | Pending |
| M1-8 | Deliver live and retained execution review with bounded item windows, exact execution overlays, task/item recording issues, terminal axes, current ledger evidence, capacity/generic-I/O messages, and informational trash location. | Test filesystem/recording combinations, overlay and omission invariants, Gap plus terminal reconciliation, navigation/re-observation, generic unrun presentation, yellow capacity without hiding known failures, bounded evidence queries, and post-copy overlay independence. Trash counts require complete outcome evidence; location-only fallback must not assert a planned count, scan all trash, or imply purge. | Pending |
| M1-9 | Deliver bounded inventory projections, current evidence, and the full inventory consumer for sibling sorting. | Test complete or prior-complete publication, warnings outside action scope, raw evidence provenance, search/filter/collapse/window/detail behavior, replacement/races, supported sort/reset production paths, and headed witnesses. | Pending |
| M1-10 | Deliver baseline, verify, and rebaseline controls plus the first same-task manual post-copy verification without persistent operation-time hashes. Rebaseline includes eligible null-evidence files and always hashes/replaces evidence; matching content is not a verified match. | Test acknowledgement admission before claim/native work; all-null and mixed rebaseline through workflow, service/CLI, and desktop; conditional-recording and supersession races; handoff classification; live pause/resume/cancel and unchanged automatic failed-read retries; and overlay/result identity boundaries. Terminal Verify-remaining/subset retry is deferred. Independently review the operation matrix and conditional-recording races. | Pending |
| M1-12 | First close integrated lifecycle/retention across activated task surfaces (absorbing former M1-11), then complete adversarial, documentation, ordinary, and headed verification. | Exercise plan-only, execution-only, linked/manual verification, inventory, refused, canceled, degraded, and failed tasks across navigation, reinjection, explicit close, and shutdown. Verify existing admission bounds, stale-response suppression, exact resource release and retained result truth; no aggregate-artifact or whole-owner-graph criterion. Run applicable settlement-oracle stability, ordinary/headed suites, installed-wheel/product witnesses, import checks, `git diff --check`, active-link checks, and independent cross-component review. | Pending |
| M1-Release | Produce beta packaging and release closure after delivery rows above are complete. | Build/test an installed artifact from a clean checkout; supply frozen specification/dependency/CI, notices and corresponding-source release material, standard-integrity host proof, and every applicable BR-G and SH-G gate. INTERFACES owns host/package and SH-G release criteria; BRIDGE owns BR-G evidence. | Pending |


## Checkpoint expansion and scope decisions

Use this lightweight expansion before each pending checkpoint, drawing on
`plan-work` without duplicating its full template. AGENTS owns the boundaries;
`execute-task` supplies the decision, waiting and recovery procedure. These
requirements remain usable without either personal skill installed.

1. Start from the accepted outcome and current repository revision. Trace the
   owners, state/effect transitions, direct consumers and harness dependencies;
   include helpers outside the initially selected directory. Record the finite
   corpus, relevant observations and remaining uncertainty.
2. Name the finite production, test and documentation population, current
   owners/seams, one acceptance gate and atomic commit boundary. State preserved
   guarantees, excluded/archived clauses and dependencies. Add only the detail
   needed to implement and review that outcome; findings do not silently become
   scope.
3. Probe likely regressions during design: lost guarantees, false states,
   unauthorized/duplicate effects and newly unbounded work. Tie each concrete
   risk to a reached seam and named verification. Record baseline evidence;
   red tests indicate a question, green tests do not prove absence of defects.
   Implementation validates this map rather than starting a broad discovery pass.
4. Require final adversarial review of source, tests, documentation and evidence
   at the checkpoint gate. Completion requires the gate and preserved baseline,
   not a favorable test count. After delivery, replace detailed working/recovery
   notes with what happened, what did not, and commit/contract/evidence pointers.

One next-checkpoint design lane may begin during the current checkpoint's final
product implementation and continue through testing, verification and review.
It is read-only toward product and test sources; serialize shared plan edits.
Record the inspected revision, then compare affected seams against the final
integrated predecessor before implementation. Refresh only changed assumptions,
consumers and probes. A current finding that changes those seams reopens that
part of the next design. Design readiness cannot waive predecessor completion,
implementation authorization or the user's pause.

Elaborating an accepted pending outcome within these boundaries is planning;
enlarging an active implementation population or its mechanism is a scope
decision. For the latter, suspend dependent edits and first complete the finite
dependency probe and one consolidated proposal. A narrow, understood extension
may obtain explicit adjudication in-turn using the available permitted input
mechanism; unanswered requests within the bounded procedure become a full stop.
Architectural or unresolved changes require a full stop with the design study.
Hard-wall stops take precedence immediately. Record approved scope before edits;
silence never expands it, and unchanged approvals are not requested again.

## M1-7 implementation and closure

The user authorized M1-7, the closing-race correction, snapshot-bound destructive
confirmation, aggregate/breakdown facts, an inert gallery preview, and confirmed
Plan-again/control consumer corrections. Stop after this checkpoint for recap and
GUI tweaks. No M1-8, DOC-2, push or PR is included. Original study revision:
`7e94598`; documentation cleanup is integrated in `a1d78ca` and `40ca76f`.

### Implemented behavior and ownership

- Workflows derive immutable Plan projections, raw sibling-sort facts and selected
  operation/risk/space totals. Selection preserves dependency closure, operation
  ordering and immutable artifact identity. Filters and windows do not redefine
  scope. The browser retains only its bounded 1–256-row window.
- TaskRegistry owns task delivery and the current session; the existing service
  and lifecycle own reviewed identity, selection commitment and admission.
  Same-task Execute requires the released planning session. Failed admission
  restores editable review; admitted execution remains committed even when fresh
  preflight refuses before effects. Original Plan replay cannot become current.
- Execute captures task/request/selection revision. Every selected destructive
  scope opens the production Fluent smoke modal. Cancel submits nothing; Confirm
  submits the same snapshot for backend validation, commitment and admission in
  one command. Exact uncertain retries retain their intent and fence selection
  and Close. Modal/background focus, pointer, wheel, Escape, animation exit and
  reduced-motion behavior are verified. The gallery starts closed and previews
  the same dialog without execution effects.
- Terminal-session release retains a task; explicit Close retires it. Close and
  follow-up admission have atomic ordering and claim revalidation after waits,
  without holding owner locks over domain I/O. Exact replay survives source-task
  retirement. Terminal records retain the exact plan/inventory/execution kind and
  capability contract.
- Current-session StateChanged events drive execution controls. A later event or
  terminal record prevents an older command reply from regressing presentation;
  Plan refresh preserves live state. Hidden Plan controls stay hidden. Plan again
  creates a fresh task under the existing 48-task limit; release does not free a
  task slot. Selecting a task after a Plan-load error performs the advertised
  guarded retry, preserving cached and in-flight views.

Behavior owners: [BRIDGE](BRIDGE.md), [PRESENTATION](PRESENTATION.md),
[INTERFACES](INTERFACES.md), [DESKTOP_UI](DESKTOP_UI.md), [FEATURES](FEATURES.md).
[BUGS](BUGS.md) records substantive corrected mechanisms. Core source remains the
authority for exact contract shapes; no dispatcher/module/db effect-policy change
was needed.

### Finite implementation and regression boundary

Production owners are workflow tree/projection/selection helpers; existing
interface service/lifecycle/task-port owners; web commands, task delivery and
Plan review; and packaged app/bridge/Plan/modal assets. Tests cover those owners
and their current setup/task-shell/gallery, event, wheel, replay/uncertainty,
close-ordering and quantitative consumers. The user-approved investigation
compared Setup, Task 47→48 and post-release Task 48→49 across button, eligibility,
attempt, bridge, host validation, registry, response and refresh boundaries.
Its bounded opt-in test trace preserves installed asset bytes and is diagnostic
only; clean installed runs establish acceptance. Raw findings are retained in
`build/m1-7/evidence/plan-again-findings.md` and its referenced records.

Regression guarantees include exact review/session identity, current-request
binding, monotonic selection revision, stale callback rejection, single admission,
Close/replay ordering, truthful committed-but-unrun status, inert hostile display
text, bounded ingress/windows and authoritative state ordering. There is no
selection reopening, terminal subset retry, execution-result overlay, inventory
projection, capacity-policy change or global-settings expansion. Archived bridge
recipes remain provenance, not renewed representation or reservation requirements.

### Acceptance evidence

**M1-7-G** combines the functional/regression checks, affected owner/consumer
neighborhood, ordinary suite, twelve import contracts, clean installed headed
flows, fixed quantitative acceptance, links/diff checks and independent review.
The fixed quantitative contract and validator were independently reviewed before
measurement. Its 35 cases retain the predeclared populations, 5 fresh children per
case, warm/cold sampling, timing endpoints and budgets. Publish-once native
fixtures use ordinary task navigation and exact fresh reviewed identities; they
do not rewrite private task state or synthesize startup events. Component memory
evidence is not an aggregate headed-memory claim.
Before startup, the fixture settles each published view sequentially through
public open/window reads and retains exact identity/revision/window proof. The
browser still selects every task and verifies the rendered source outside timing.
This prepares the interaction cases' declared current-review state; it does not
establish concurrent cold-start latency. Separate cold-construction cases retain
their original limits. The recurrence pause and independent reorganization
review distinguished the corrected selection-retry consumer from fixture setup;
no product scheduling or transport deadline was changed.

The source-owned quantitative population is `tests/plan_review_benchmark.py` and
`tests/interfaces/web/_plan_review_scale.py`, `test_plan_review_scale.py`,
`m1_7_plan_contract.json`, `m1_7_plan_authority.json` and
`m1_7_plan_measurements.json`. The contract enumerates the 42 measured source
paths, 38 installed product paths and finite runtime roles. Hash inclusion grants
no implementation authority over otherwise excluded owners. PRESENTATION and
BRIDGE own the unchanged budgets, profile and sampling procedure.

Acceptance requires frozen physical source/wheel/installed bytes, the finite
direct runtime corpus, fixture and profile, plus genuine raw measurements
validated independently against the fixed criteria. Git-clean HEAD identity
must be checked separately after the checkpoint commit. Any measured
source/runtime/profile change requires the corresponding rebuild and rerun.

Current verification:

| Gate | Evidence / state |
| --- | --- |
| Ordinary repository | 5,083 passed; four platform-capability skips and one pending scale-artifact skip. `ordinary-20260914-230402.txt`. |
| Installed desktop | 30 passed in `headed-20260914-222005.txt`; final affected task-flow rerun passed in `headed-20260914-230854.txt`. Unchanged desktop cases remain valid. |
| Focused / layering | Frontend static 48 passed; twelve import contracts passed (`imports-20260914-222917.txt`). Closing race has 532 owner tests plus twelve ordering and nine retained-consumer checks. |
| Independent review | Product, consumer and fixture diffs pass. Measurement provenance/completeness passed independent review; fixed acceptance failed on 12 metrics, blocking closure. |
| Quantitative | Full readiness passes 15 children / 35 cases. The single measurement run completed 175 children / 775 samples; provenance validates, but 12 of 35 metrics exceed fixed criteria. Raw artifact and complete collection retained under `framework-20260915-155500/`; stopped without repair or rerun. |

Logs above live under `build/m1-7/evidence/`. The latest quantitative wheel is
`6811e25f018296117ee86330febf36ab05d11fa602695134e24e78af795525a8`;
all 38 physical source/wheel/installed product files match. Current contract SHA-256:
`0c82a7044348193af2d68b25c6645263e15c4f532f4015257324c33227b930c3`.
Readiness repairs passed 46 owner tests with one pending-artifact skip, the final
listener control and same-control ablation, and four affected watchdog controls.

The bounded trace in `plan-load-trace-20260914232426/` records 17 complete
observations: initial loads and the admitted selection retry exhaust the two
5-second open-view transport attempts, before window reading. A later public
read returns the exact current view. This is diagnostic evidence of the reached
boundary, not proof of native handler counts or the sole cause of the delay.
The reviewed fixture barrier establishes the interaction cases' declared initial
state; it does not close concurrent cold-start latency.

### Recurrence review and current containment

Three unplanned product defects triggered the AGENTS pause. No further instance
fix began before the mechanism table and independent reorganization review:

| Mechanism | Consequence / owner | Disposition |
| --- | --- | --- |
| Hidden-state cascade | Unbound loading controls remained visible; Plan CSS/null projection. | Scoped hidden rule and focused/installed witnesses pass. |
| Unordered live-state projection | Pause/Resume and refreshed terminal truth regressed; app event/receipt/refresh arbitration. | Closed ordering matrix and installed control flow pass. |
| Missing recovery dispatch | Selection did not perform the advertised Plan retry; app selection/load guard. | Guarded eligible-task retry; open/window failure, duplicate, stale and cached-view probes pass. |

The orchestrator accepted the independent narrow reorganization under the user's
existing confirmed-cause authorization. These defects meet at browser task/review
orchestration but do not justify another lifecycle owner. No eager-load,
coalescing, transport-deadline or effect-policy change is included. The sequential
fixture preparation is separately reviewed as untimed initial-state settlement.
BUGS records the corrected product mechanisms; raw evidence retains investigation
details. No new diagnostic or repair loop is authorized by this record.

### Integration and stop

**P8 shared structure (base `90d9469`, authorized 2026-09-16): completed;
stop after focused measurements.** Core `ExecutionSetCheckpoint` and workflow
checkpoint materialization share the constructor-validated immutable structure
while reopening fresh mutable overlays. Public constructor and admission checks,
exact plan/selection/deselection identity, verify/resume state, commitment time
and receipt-after-admission remain intact. Generic callback authority snapshots
stay cheap/nonvalidating. No duplicate index, review cache, dispatcher change or
legacy model; ARCHITECTURE accounts for the index's extended paused lifetime.

Closed population: `core/execution.py`, `workflows/models.py`, direct domain
checkpoint tests and bridge-resume/post-execution consumers; matching
ARCHITECTURE/INTERFACES notes, HANDOFF and CHANGELOG. Sharing/non-reconstruction,
mutable isolation, malformed/mismatched state and public refusal witnesses pass.
Focused corpus: 259; ordinary: 5,157 passed (5 skipped / 30 deselected); imports:
12 kept; installed Plan: 1 passed (2 deselected); independent source review passes.

One receipt readiness child and five fresh measurement children completed
30 samples: p95 **72.0 ms**, maximum **72.9 ms**, passing unchanged 100/250 ms
limits. Previous p95/max: 121.9/122.7 ms. Range 43.5–72.9 ms; per-child maxima
58.2/66.6/72.0/72.0/72.9 ms. Evidence remains diagnostic, not full M1-7 acceptance.
Raw receipts and source/installed/runtime identities are retained under
`build/m1-7/evidence/p8-structure-20260916/`. Supplemental provenance freezes
the changed `core/execution.py` source/installed/wheel triplet outside the
historical contract's file list; protected contracts/evidence remain untouched.
Independent `comparison/evidence-audit.json` verifies all six children, raw
links, statistics and declared/supplemental source, build and runtime identities.

One atomic verified commit preserves this outcome. Stop after this round:
no retry, further profiling/optimization, full run, threshold change, amendment,
merge or pruning. Prior recovery history remains unchanged.

**P7 digest reuse (base `a479e58`, authorized 2026-09-16): completed; stop
after focused measurements.** Closed population: workflow selection/runtime,
service preview, direct workflow/service tests and the existing benchmark's
normalization/digest helper; INTERFACES owns the behavior/retention account.
Prepare one canonical 32-byte digest with the exact-plan/deselection-bound
decision; reuse it for review, preview and commitment. Preserve currentness,
revision/acknowledgment, fresh commitment time, public constructor validation and
actual admission/custody/publication before receipt. No extra index, legacy input
adapter, core/dispatcher change or protected contract/evidence mutation.

The bounded attribution used one component probe (warmup + five observations)
and one installed headed child (warmup + six). Headed medians: digest 51.654 ms,
two `ExecutionSet.__post_init__` calls together 76.292 ms, other service
admission 10.320 ms; service total 140.381 ms and browser receipt 142.700 ms.
Separate timing domains do not establish bridge-only duration; phase medians
need not sum. Component-only observations remain separately labeled.

Verification: canonical equivalence, no repeat hashing, fresh timestamps,
identity and mutation/replacement witnesses pass; focused workflow/service 82,
scale contract 1, ordinary 5,153 (5 skipped / 30 deselected), imports 12, installed
Plan 1 (2 deselected), independent source review. Receipt readiness and one
five-child/30-sample comparison completed: p95 **121.9 ms** versus 100 ms;
maximum **122.7 ms** versus 250 ms, improved from 170/175.4 ms.
Range 79.8–122.7 ms; per-child maxima 112.5/122.7/104.4/121.9/114.9 ms.
P95 remains non-passing. This is diagnostic comparison, not full acceptance.

Evidence: `build/m1-7/evidence/p7-receipt-20260916/` retains raw attribution,
source/installed/runtime identities and `comparison/` authority/child receipts.
Independent `comparison/evidence-audit.json` verifies all six children, 30
samples, raw links and frozen source/installed/wheel/runtime identities.
One atomic digest-first commit includes matching tests/docs. That round stopped
without retry, further optimization, full run, threshold change, amendment,
merge or pruning. P8 above owns the subsequent checkpoint structure-sharing work.

**P6 resumption (base `28c7b44`, authorized 2026-09-16):** investigate and fix
the observed busy-close cancellation-drain failure, considering ordering/timing
and comparison with `353092b`; finish the named selection-retention evidence
gaps, then run the focused comparisons. Initial finite cause corpus: the failed
test and its registry drain/close, service delivery/cancel and dispatcher event
publication seams. Preserve reliable event order/exactly-once cancellation and
truthful pending close; do not prescribe a one-batch observation unless that is
the product contract. Record the confirmed correction population before editing.
Selection evidence population is the existing service/projection/drain owners'
tests; no new product behavior is implied. Focused regression, ordinary/import,
installed Plan and independent-review gates precede existing untimed readiness
and one eight-metric comparison round. No repeated optimization/measurement
loop, criterion changes, full run, amendment, merge or pruning. Stop on a new
unresolved functional/harness blocker or repository mandatory stop; the prior
named cancellation observation is now authorized for correction.

Confirmed cancellation correction population: the named test in `test_drain.py`
only. Dispatcher CANCELING publication precedes asynchronous SessionObserver
delivery into the task adapter; a 0.1 s test drain may return before that handoff.
The exercised cancellation code and test match `353092b`; prior passes do not
establish same-next-batch delivery. Use a controlled delayed-offer reproducer
and an actual adapter-offer readiness witness, preserving ordered single-event
delivery, repeated pending close and retained task assertions. No production
change, sleep or timeout increase.

Resumption verification: the corrected cancellation case and busy-close
neighborhood pass; the selection owner file passes 36 tests, closing all named
retention gaps. Independent review passes. Ordinary suite: 5,152 passed,
5 skipped / 30 deselected (260.57 s); imports: 12 kept; installed Plan GUI:
1 passed / 2 deselected (44.26 s). No product source files changed during this
resumption. The prepared diagnostic driver was corrected before use to apply
maximum, not the 30-sample p95 helper, to five cold memory samples, and to
record/check its own hash. Protected measurement artifacts are unchanged.

The single focused round completed 23 untimed readiness cases in three
processes, then 40 measurement processes / 215 samples for eight metrics.
All six changed sorts pass: filename asc/desc p95 0.728396/0.737502 s;
size asc/desc 0.751273/0.728179 s; mtime asc/desc 0.746687/0.746219 s.
Their maxima are all below 0.770 s, versus fixed p95/max limits 1.5/3 s.
Memory overlap maximum is 279,744,512 bytes (266.785 MiB), down from
443,437,056 bytes (422.895 MiB); the 320 MiB criterion needs no adjustment.
Execution receipt p95/max are 170/175.4 ms, improved from 283/284.1 ms.
Its maximum passes 250 ms, but p95 still fails 100 ms: seven of eight focused
metrics pass. These are diagnostic comparisons, not a new full terminal
acceptance artifact. Stop after this round without another optimization,
measurement, full run or integration. Raw children, runtime/source/installed
authority, dispersion and aggregate report are retained in
`build/m1-7/evidence/p6-resume-20260916/comparison/`.
Independent evidence audit verifies all 43 unique process/child/token identities,
215 samples, linked receipt hashes, 42 source files, 38 installed/wheel members,
14 runtime roles and driver/contract/interpreter identities against the frozen
authority; `comparison/evidence-audit.json` records that audit, not acceptance.

**P6 budget correction (base `4a01b2c`, authorized 2026-09-16):** implement
the three proposals below, then return with updated targeted measurements.
Finite production population: workflow projection/order and selection facades,
service selection lifecycle, PlanReview callers and their direct tests. Root
owns PRESENTATION/INTERFACES, this register, HANDOFF and CHANGELOG updates.
The direct PlanReview registry selection-refresh consumer is included so
membership remains shared after edits as well as initial projection creation;
its revision/currentness checks and external DTO/wire shape remain unchanged.
Projection sort/construction form one atomic outcome; shared selection follows
its overlapping projection seam as a second outcome. No early core execution
structure, six-order cache, dispatcher redesign, new runtime model or changes
to protected evidence/criteria. Preserve the archived evidence-reader-only
disposition and all public validation/admission guarantees described below.
Focused regression/equivalence and ownership/lifetime checks, ordinary suite,
import contracts, installed Plan GUI and independent review precede quantitative
collection. Run the existing untimed readiness for each measured interaction,
then one fixed five-child comparison for each of the eight failed metrics;
collect this round's results without optimization/retry loops. Stop on functional,
readiness, harness or repository mandatory-stop failures. Budget misses are
reported after this round, not repaired in another pass. The 320 MiB criterion
remains unchanged; a moderate residual may be discussed only after measurement.
No full measurement run, amendment, merge or pruning in this round.

The original P6 pass was preserved at `28c7b44` after the cancellation test
failure, before measurements. Its focused evidence remains under
`build/m1-7/evidence/p6-budget-20260916/`. The authorized resumption above fixes
that fixture assumption and fills the service-level projection-sharing,
close-release and complete exclusion/fact verification gaps. Independent source
review and focused correction tests pass; final gates and targeted results
belong to `build/m1-7/evidence/p6-resume-20260916/`.

**Remaining budget study (base `353092b`, read-only):** investigate the six
changed-sort p95 failures, retained review memory and execution-start receipt.
Close over retained compact artifacts and exact benchmark boundaries; projection/
ordering/visible-state construction; bridge/service/registry/runtime admission;
and direct owner tests. Separate measured outcomes from source-based cost
candidates. Return one bounded resolution proposal with preserved guarantees,
consumer scope and verification; no product/test changes, profiling, measurement
reruns, threshold changes or integration before discussion.

Study outcome: six changed-sort p95 values are 1.629–1.861 s versus 1.5 s
(all maxima pass), peak review-construction overlap is 422.895 MiB versus
320 MiB, and start-receipt p95/max are 283/284.1 ms versus 100/250 ms.
These are end-to-end observations, not measured function-level attribution.
Proposed corrections, approved for P6 above:

- **Sort:** derive real orders in the workflow owner from cached canonical
  sibling order. Stable-sort available raw primary values and append unavailable
  siblings in canonical tie order, avoiding comparator-sorting 120,000 notice
  rows. Privately publish generated orders; retain public malformed-input
  validation, immutable nodes/inverse maps and atomic view publication. Scope:
  projection/order owner, PlanReview caller and projection/review/visible/scale
  witnesses. No six-order cache or further visibility redesign.
- **Memory:** use private slotted drafts, release completed tree/index
  intermediates before materialization and stream warnings. Materialization
  already clears consumed drafts; earlier coexistence remains. Preserve final
  projection shape, identities, peer links and selection facts. Scope:
  projection builder and owner/scale tests. The sampler measures process-private
  peak while two reviews coexist, not final buffer sizes; no retained phase data
  establishes which allocation dominates or guarantees recovery of 102.895 MiB.
- **Receipt:** reuse the workflow-derived decision already computed for review,
  bound to exact plan/deselection identity and atomically refreshed with revision
  changes. Share its selected membership with projection state rather than
  retaining another independent O(N) set. Scope: service selection state,
  preview/admission, workflow projection/selection and direct web/runtime
  consumers. Preserve runtime authority checks, destructive acknowledgment,
  and actual admission/custody/publication before receipt. Defer a new reusable
  core execution structure: that would transfer validation earlier and extend
  index lifetime. The review-only memory fixture does not account for additional
  service caches. Account for the full decision, exclusions and preview DTOs,
  including replacement, invalidation and task-release lifetimes; sharing
  membership alone does not establish no net memory increase. This accounting
  is an acceptance requirement alongside the unchanged memory comparison.

Proposed verification: independent sort equivalence/public rejection,
projection/peer/notice/selection parity, shared membership and cache invalidation,
stale revision/artifact rejection, admission replay/rollback/custody, and relevant
owner/consumer suites. Untimed readiness precedes one targeted comparison per
failed group under unchanged fixtures and budgets; stop at the first failure.
Another full run requires passing comparisons and user authorization. No
product/test changes, profiling or measurements occurred during this study.

**P5 GUI repair (2026-09-16; base `1c14ccc`, full-measurement stop):** investigate
the retained `page_plan_review_plan_ack` runtime error and fix its confirmed
cause. Initial finite corpus: task-shell headed scenario/confirmation driver,
existing driver and frontend tests, retained native failure/driver records, and
production confirmation/PlanReview consumers reached by that evidence. Record
the exact fix population before editing. Preserve reviewed execution snapshot,
modal input blocking, backend admission and all quantitative criteria. No
diagnostic campaign, old representation generation, unrelated optimization or
amendment/merge/pruning. One atomic fix includes owner tests and matching docs;
independent review and relevant ordinary/installed checks precede acceptance.
After acceptance, run untimed component readiness and one changed-search gate
(five children / 30 samples, p95 <= 1.5 s and max <= 3 s). Only on pass freeze
the compact authority, run full untimed readiness and the fixed full measurements
once; stop afterward regardless of result. Stop at the first non-passing
verification/readiness/measurement condition, without a repair/rerun loop.

Confirmed repair population: `_task_shell_headed_child.py` and its existing
`test_task_shell_headed.py` owner guard; no product changes. The retained record
shows committed selection, running execution and a closed dialog while the page
stage remained `confirm-open`. Page/native polling can miss `data-closing`, which
has no minimum duration under the product contract. Arm a finite tests-only Web
Animations barrier before each trusted Confirm (refused and live cases); release
after the required closing-pointer or Enter acknowledgment witness. Production
still owns modal closure and immediate admission. Preserve the native blocked
input assertions, zero-motion product behavior and existing 120-second scenario
watchdog. Verify the owner/static/frontend checks, interfaces department, and
the installed Plan gate once; retain the already passed generic-tree gate and
ordinary product baseline when their bytes/seams remain unchanged.

Result: the tests-only paused animation barriers and durable live-confirmation
acknowledgment pass independent review, 50 focused tests, 1,667 interfaces tests
(one pending-artifact skip), and the installed Plan gate. All 38 product files
match source/wheel/installation; the prior ordinary/import/generic-tree gates
remain applicable to unchanged product bytes. The 21-case untimed component
gate passes. The single 30-sample changed-search comparison passes p95
**151,705,000 ns** / maximum **153,806,600 ns**. Compact authority was frozen;
all 35 readiness cases across 15 processes then passed.

The one full run collected **175 children / 775 samples / 35 metrics**. Terminal
validation rejects fixed budgets: **27 metrics pass, 8 fail**. Six changed-sort
p95 values are 1.629–1.861 s against 1.5 s (all maxima meet 3 s); retained memory
is 443,437,056 bytes against 335,544,320; execution-start receipt p95/max are
283/284.1 ms against 100/250 ms. The extended compact memory workload is not an
apples-to-apples baseline comparison with the old projection-only measurement.
Stop after this run as requested: no further diagnosis, optimization or rerun.
Evidence: `build/m1-7/evidence/plan-ack-fix-20260916/`, including the copied prior
driver record, targeted comparison, readiness, complete collection and summary;
new compact authority/raw artifacts are under `tests/interfaces/web/`. Preserve
separately on the recovery branch; M1-7 remains unmerged.

**P5 compact order/metadata (2026-09-16; base `44a6856`, GUI prerequisite stop):**
the user approved the reviewed order/metadata redesign and corresponding
verification migration. Deliver it as one coherent correction on the existing
recovery branch. The production builder owns the four source/facade files and
three owner tests named below; one workflow-owned compact-buffer value/helper
and its facade export may support both consumers. The verification builder owns
the benchmark, scale validator/tests, generic-tree fixture and versioned evidence
schemas/paths; agree the API before dependent edits. Root owns shared docs and
runs; a fresh reviewer checks the complete change and evidence before commit.
Record exact added helper/version paths before editing. Retain prior protected
bytes and validate versioned successors, including the actual cached orders,
visible buffers and staging overlap. No compatibility reconstruction may hide
the new representation from measurement. Public window/selection semantics,
fixture populations, all 35 budgets, sample counts and aggregation remain fixed.

Gate: focused owner/reference/adversarial checks, direct consumer and ordinary
suite, import boundaries, fresh installed Plan/generic-tree gates, independent
source/verification review, and untimed readiness before sampling. Then run one
changed-search comparison (five fresh children / 30 samples, p95 <= 1.5 s and
maximum <= 3 s) on matching installed bytes. If it passes, freeze the final
versioned authority, complete all 35 readiness cases, and run the full fixed
35-metric / 175-child measurements once; stop afterward regardless of result.
If the targeted latency fails, investigate remaining costs read-only over the
changed-view call chain and retained samples, then stop for discussion without
another fix/run. Readiness or harness prerequisite failures return to discussion;
repository safety/recurrence stops remain. No integration, pruning, amendments
of previous commits, criterion relaxation or unrelated framework expansion.

P5 agreed production API: `CompactUnsignedIntegers` and `PlanProjectionOrder`
live in the existing workflow projection module and are facade-exported; no
extra production file. The compact value owns immutable bytes with explicit
width/count validation. Order values reference the current source projection
and compact forward/inverse indexes. Cached order references must rebind on
selection-only replacement so no earlier projection is retained accidentally.
P5 verification successor paths are
`tests/interfaces/web/m1_7_plan_compact_{contract,authority,measurements}.json`
(contract v5, authority v4, raw v5). Runner/validator select the explicit family;
legacy protected JSON remains unchanged. The generic-tree fixture and its
conftest/frontend/headed direct consumers are in the migration population only
where their representation assumptions change; preserve wire fixtures/schema
where possible. The representation manifest covers actual cached orders and
compact buffers, including sharing and construction overlap, rather than an
old tuple representation manufactured for verification.
Successor memory workload explicitly extends the old two-projection sample:
retain a 120,000-row base review with canonical and filename-descending orders
and a current 256-row window, then construct the equivalent 240,000-row heavy
review while the base remains live. Sample through projection, order and visible
construction; assert populations, sharing, compact buffer sizes and both windows.
Keep the existing metric ID, five cold children, private-byte baseline/sampler,
maximum statistic and 320 MiB limit. Only the successor declares this added
representation coverage; earlier artifacts retain their original meaning.

P5 finite population: `workflows/{plan_projection,__init__}.py`,
`interfaces/web/{plan_review,visible_sequence}.py`, their three owner test files,
benchmark/scale validator and tests, generic-tree fixture, and matching
ARCHITECTURE/PRESENTATION/delivery docs. The regression study also covered
service/drain and generic-tree headed/frontend consumers. The design review is
preserved in `44a6856`; this implementation preserves source topology, raw sort
keys/ties, selection semantics, public rejection, atomic publication, collapse,
anchors and accessibility across 256-row boundaries. Independent review confirmed
the completed code/framework correction; legacy compatibility reads historical
evidence only, without an old generator or a second product/runtime model.

P5 result: 100 owner tests, 54 scale tests (one pending-artifact skip), 123 generic
fixture/frontend tests and 12 import contracts pass. The ordinary suite passes
5,140 tests with 5 skips / 30 headed deselections. Fresh installed GUI checks
return **1 failed, 1 passed, 7 deselected**: Plan fails at
`page_plan_review_plan_ack` with `RuntimeError`; generic tree passes. The retained
failure/final records establish the stage and host return, not the cause. This
reaches the explicit prerequisite stop. No readiness, comparison, authority
freeze, full measurements, failure fix or rerun followed. Preserve the separate
P5 recovery change and `build/m1-7/evidence/compact-view-20260916/`; latency remains
unknown for this candidate. Discuss the failed GUI prerequisite before resuming.

**P4 changed-view derivation (2026-09-15, targeted-budget stop; base `b3f092d`):** the user
authorized four scan/allocation optimizations and structural investigation as one
atomic correction on the existing recovery branch. Population:
`interfaces/web/{visible_sequence,plan_review}.py`, their two owner test files,
and matching PRESENTATION, M1_PLAN, HANDOFF and CHANGELOG documentation. Builder
and fresh reviewer roles are separate; root owns shared docs. Matching/retention
are fused, empty/ASCII search has safe shortcuts, and Plan filters use a positional
mask. Preserve exact Unicode folds, public validation, weighted counts, ancestor/
collapse/accessibility semantics, ordering, selection, atomic publication and the
256-row bound. No cache, schema, domain, admission, renderer or framework changes.

Regression corpus: both owners and their tests, the workflow projection/sort
producer, service/drain consumers, benchmark and scale harness, and generic-tree
fixture/headed consumers; all remain unchanged. Retired cache/byte-wall recipes
remain retired. Gate: owner/reference/Unicode/access controls, interfaces and
projection tests, installed Plan/tree gates, independent review, 21-case untimed
readiness, then one unchanged-budget changed-search comparison (five fresh
children, six samples each). Stop after comparison regardless of result or earlier
on readiness/harness failure; safety/recurrence stops apply. No full run, other
metrics, budget relaxation, integration, pruning or amendment of earlier commits.

P4 result: four corrections implemented and independently reviewed; final owner
tests 85 passed, interfaces department 1,652 passed / one existing artifact skip,
projection producer 7 passed, installed Plan/generic-tree GUI gates 2 passed,
and all 21 untimed component readiness cases passed. All 38 measured product
files match source/wheel/installation. The one comparison retained five fresh
processes and 30 correct samples: p95 **2,295,682,100 ns** exceeds 1,500,000,000;
maximum **2,318,180,200 ns** meets 3,000,000,000. Previous p95 was 2,721,463,000 ns.
All measured source hashes remain unchanged. Evidence is preserved separately at
`build/m1-7/evidence/sparse-view-20260915/`; `views/comparison.json` explicitly
marks the group incomplete/failed, not terminal acceptance. No further metric
or implementation followed. Preserve P4 as a separate recovery commit and
return to discussion; earlier commits and `milestone1` remain untouched.

P4 structural investigation: `PlanReviewState.update` always re-enters
`sort_plan_projection` through `_derive_view`, even when only search, filters or
collapse changed. Reusing the already current `_ordered` projection is the next
bounded candidate; it must preserve selection overlays and rebuild on actual sort
or projection replacement. This pass does not implement it. A persistent folded
display index would add retained strings while memory acceptance is still open;
defer it. Incremental visible metadata would require explicit invalidation for
sibling counts, anchors and hidden retained descendants, so it is a wider design
than these scan reductions. These are source-backed proposals, not measured
attribution of the remaining latency.

**Correction authorization (2026-09-15, stopped at targeted budget):** implement the reviewed I1–I3
corrections and investigate/optimize rapid-scroll refresh churn, including windows
larger than 256 rows. Base `90c26cc`; preserve prior history and failed evidence.

| Row / atomic outcome | Production/test population and regression seams | Gate / status |
| --- | --- | --- |
| P1 projection/view allocation | `workflows/plan_projection.py`, `interfaces/web/{plan_review,visible_sequence}.py`; projection, visible-sequence and plan-review owner tests. Combine I1/I2 because materialization is shared. Preserve exact identities, peer links, raw sort/tie order, public rejection, selection and atomic replacement. | Implemented; 77 focused tests, 21 component readiness cases and review pass. First targeted metric fails p95; remaining view and memory comparisons not run. |
| P2 execution admission work | `interfaces/service.py`, `workflows/{runtime,selection,models}.py`, `core/{execution,planning}.py` and facades/direct consumer tests. Preserve plan/revision binding, destructive acknowledgement, external validation, root freshness, rollback and admission ordering. | Implemented; focused/consumer tests and independent safety review pass. Receipt comparison not run after P1 stop. |
| P3 scroll refresh | Packaged Plan/generic tree renderers, app window-fetch integration and their JS/Python/headed probes. Trace viewport coverage, debounce, in-flight supersession, render identity and disposal for small and multi-window populations before editing. | Complete: 48 frontend tests, deferred app callback races, 2 installed GUI gates and independent review pass; no generic-tree production change required. |

Root owns shared docs; builders record any newly identified direct consumers
before editing. P1's unchanged direct consumers are `workflows/__init__.py`,
`interfaces/service.py`, `interfaces/web/drain.py`, `tests/plan_review_benchmark.py`,
`tests/interfaces/web/{test_plan_review_scale,_tree_window_fixture}.py`, and
serialized headed/JS windows; include them in regression review without changing
their authority. P2 adds review of `workflows/sync.py`, workflow facade, direct
selection/resume/workflow/checkpoint/post-execution/preflight/settings/CLI tests
and their fixture helpers; retain forged-input and mutable-overlay rejection
while reusing only owner-proven immutable facts. P3 closes over `assets/app.js`,
`assets/plan_review.js`, `tests/assets/plan_review_probe.mjs` and
`tests/assets/task_shell_probe.mjs`, with `tests/interfaces/web/test_frontend_static.py`;
generic `tree.js`/its probe already
implement coverage/generation handling and remain read-only regression consumers.
Existing retired byte-wall/cache
recipes remain retired. These
are performance corrections, not authority/schema, selection-policy or inventory
feature changes. No budget relaxation, previous-artifact replacement, broad
diagnostic expansion, full 175-child run, merge or branch cleanup in this pass.
Use focused owner checks during implementation and the ordinary suite plus
appropriate headed consumer gate after integration. One bounded diagnostic per
failed group may attribute work before targeted checks; a failed targeted budget
check returns to discussion, without another optimization/measurement loop.
Apply repository safety/recurrence stops; preserve any incomplete outcome here.

**Correction result:** P3 is independently committed as `82d27bc`. P1/P2 remain
quantitatively incomplete and are preserved separately. In the one attempted
metric, five fresh children / 30 samples give changed-search p95 2,721,463,000 ns
(limit 1,500,000,000) and maximum 2,845,864,400 ns (limit 3,000,000,000).
The unchanged instrument's correctness checks pass. This diagnostic comparison
does not replace the old acceptance artifact. Evidence is under
`build/m1-7/evidence/corrections-20260915/`; no further metric, optimization,
freeze, full run or integration followed the failed p95 check. Stop for discussion.

**Investigation authorization (2026-09-15, completed; discussion stop):** inspect the three failed
measurement groups and discuss findings before any fixes or measurement reruns.
Use the retained run at `eb53f5b`; source and artifact inspection only. No product,
test, instrument, authority or budget edits; no native run, benchmark or profiling.

| Study | Finite corpus and outcome | Closure |
| --- | --- | --- |
| I1 | Ten changed-window timings: retained samples, benchmark transition/setup boundaries, PlanReviewState, visible sequence and projection direct calls. Identify shared work and compare passing cases. | Source-backed mechanism, evidence limits, proposed correction and later verification. |
| I2 | Projection/staging memory: retained samples, accounting roots/baseline, projection and view representation, PRESENTATION/DEFENSE ownership. Distinguish retained population from accounting effects. | Same, with population/overlap accounting. |
| I3 | Typed Execute receipt: retained samples, observer endpoint, production bridge/registry/service commitment/admission and fixture substitution. Compare passing click/control and component commitment cases. | Same, without inferring where elapsed time was spent from the total alone. |

I1–I3 source/artifact studies are complete; [HANDOFF](HANDOFF.md) records findings,
uncertainty and the consolidated correction/verification proposal. Repeated full
view rebuilding, overlapping projection construction, and duplicate execution
selection/validation are confirmed; exact timing/byte attribution is not. Active
fixture workers also accumulate during receipt samples. No implementation or
rerun followed. Stop for discussion; earlier commits and recovery branch remain
preserved, with no integration or cleanup authorized.

**Measurement authorization (2026-09-15, completed):** run the fixed 175-child
measurements once from `325b0a6`, after verifying unchanged authority and the
completed 35-case readiness. Use the retained
`framework-20260915-155500/` inputs and fresh measurement children. Preserve
incremental receipts and the final outcome; stop and recap regardless of result.
No retry, repair, refreeze, criteria change, integration or branch pruning.

**Current result and stop:** the one run completed 175 distinct children, 35
metrics and 775 samples with valid provenance and a complete retained collection.
Strict acceptance failed. Ten changed-window metrics exceed 1.5-second p95 and
3-second maximum budgets (p95 4.396–6.143 s; maxima 4.415–6.258 s); projection
staging memory is 525,881,344 / 335,544,320 bytes; typed Execute receipt is
520.4 / 100 ms p95 and 523.7 / 250 ms maximum. The other 23 metrics meet criteria.
No cause investigation, repair or rerun follows. Raw artifact SHA-256 is
`345c2fcc14517218ce57741967594cb10ce690e6696604e69a619af22df50c13`.
Preserve this failed acceptance result separately; M1-7 remains unmerged.

**Readiness repair authorization (2026-09-15, completed):** the user authorizes
investigating and fixing the remaining readiness issues. Resume from `f1a33a3`
on the same recovery branch; retain all earlier commits unchanged. Close the
read-only study over all 13 headed setup/action/observation paths, their fixture
builders, public bridge/UI contracts and existing focused controls before
implementing the confirmed common corrections. This supersedes the previous
stop-at-first-readiness-issue instruction for repairs within that population.
Product behavior, criteria, fixture scale, sample counts, automatic evidence
reuse and expensive measurement runs remain outside this repair pass.

| Repair row | Outcome and finite scope | Gate | Status |
| --- | --- | --- | --- |
| R1 | Align all remaining headed readiness setup/action/observation paths with existing public contracts; begin at Confirm's typed-receipt timeout. Runner and focused scale tests own corrections; add validator/contract changes only if a confirmed direct consumer requires them, recorded before editing. | Closed regression study, executable fault controls, focused tests, independent source review, fresh authority and complete 35-case readiness. | Passed |
| R2 | Investigate the grouped component readiness child's 300-second process timeout under the user's remaining-readiness repair scope. Runner process orchestration and owner tests only; preserve the 21-case group, 15-child/35-case total, correctness and measurement budgets. | Establish watchdog ownership and a finite justified correction before editing; focused orchestration control, independent review, refreshed authority and full readiness. | Passed |

One separate coherent correction commit includes owning PRESENTATION guidance,
delivery records and fresh authority. Preserve each attempt's evidence. Stop for
product/contract changes, unresolved ownership or the repository recurrence and
safety conditions; do not widen into a diagnostic campaign. Finish readiness and
recap before starting any fixed measurement run or integration.

R1 confirmed cause: `observeStartReceipt` defined/removed its handler but had never
registered it with `chrome.webview.addEventListener`. Existing retained database
evidence shows Confirm admitted a running execution, while this observer could
only time out. Nine remaining headed IDs share the helper (Confirm,
nondestructive Execute, typed Execute and six control cases); the one-row read
does not. Correct the missing registration in the runner and add executable
EventTarget delivery/cleanup controls in `test_plan_review_scale.py`. The absent
registration must fail the same control. No native cause probe is needed after
that reproducer; remaining fixture/criteria/validator/contract stay unchanged.
This is one predeclared common-helper correction across the nine consumers,
followed by fresh full readiness, not nine independent instance fixes.
The full owner test file passes 46 tests with one pending-measurement-artifact
skip; the final multi-listener control passes independently. Source/wrapper
review and fresh Prepare/Freeze pass. The new evidence directory is
`build/m1-7/evidence/framework-20260915-153500/`; the previous directory retains
the failed readiness receipts and observer regression evidence.
The refreshed pass accepted selection then stopped at the component group's
300-second process watchdog, before reaching Confirm. R2 closes only that grouped
orchestration boundary; this is the second distinct readiness issue in this pass.
No measurement began and no incomplete readiness has been accepted.
R2 correction: retain the existing 300-second child watchdog for every measured
child and all other readiness children; give only the fixed 21-case component
readiness group a 600-second parent-process allowance. This operational hang
guard is not a timing acceptance budget. The prior same group completed in
240.724 seconds; the current timeout alone cannot distinguish slow work from a
stall. Add only a timeout argument at the subprocess seam and focused controls
proving the sole grouped override and unchanged defaults. No progress protocol,
schema, validator, contract, sample or fixture change. After review/refreeze,
one full readiness attempt follows; another timeout or substantive issue stops
for review rather than increasing the allowance again.

**Repair completion:** both corrections pass independent source review. Fresh
authority `e068a5d36045247f0329a20251d13dee97e693d8d7eb1143030c79db3f2cef63`
passes independent workspace validation (42 source, 38 installed, 14 runtime
owners; unchanged contract, product, runtime/profile and fixtures). Full readiness
passes all 35 cases in 15 distinct children under
`build/m1-7/evidence/framework-20260915-155500/`. That repair stop preceded the
separately authorized measurement run recorded above; M1-7 remains unmerged.

**Framework authorization (2026-09-15, preceding):** implement the independently
reviewed `build/m1-7/evidence/framework-review-20260915.md` proposal. Preserve
`cf5a00b`, `30d35f3`, `fdc7c1b` and the current recovery branch; all new commits
remain separate. M1-7 stays unmerged. Stop at any newly exposed prerequisite,
readiness or substantive issue; no new diagnostic or repair campaign. If all
correction gates pass and measurement is warranted, run the fixed set once and
stop for recap after it finishes, regardless of result. Do not integrate/prune.

| Framework row | Accepted outcome / finite owners | Verification | Status |
| --- | --- | --- | --- |
| F1 | Runner selects an exact eligible operation; proves pending warmup and authoritative revision/row settlement through synchronous public views. No product edit or pending-frame relaxation. | Focused disabled/stale/eligible and false-warmup controls; selection first in the single readiness pass. | Source/review/native readiness pass |
| F2 | Exact 35-case untimed readiness coverage in 15 children: shared 21 non-memory component cases, isolated memory construction, 13 fresh headed cases. Same action/correctness paths, full fixtures; no measurement samples or state reuse. | Exact coverage, identity, cold/memory semantics and measurement refusal without valid readiness; independently reviewed new authority and one readiness pass. | Source/review/full native readiness pass |
| F3 | Atomic retained child receipts and an incomplete sidecar index; unchanged terminal receipt/run schemas and complete-case validator. No automatic reuse. | Failure/interruption retention and incomplete/missing/duplicate/tampered evidence controls; final source review. | Source/review and retained-evidence validation pass |

Code/test population is `tests/plan_review_benchmark.py`,
`tests/interfaces/web/test_plan_review_scale.py`, and the minimum contract or
independent-validator changes needed for readiness/provenance. New authority and
genuine measurement artifacts use their existing paths; old evidence is preserved
before replacement. PRESENTATION owns the procedure; this register, HANDOFF and
CHANGELOG own delivery records. Existing installed product bytes and smoke remain
valid only after changed-seam review; the instrument change requires a fresh
authority. Focused framework gates replace no existing product gate, but unchanged
functional evidence need not be rerun. One coherent separate framework commit
includes tests/docs/authority after verification; any earlier stop preserves new
work separately. Sampling, budgets, scale, production behavior, automatic resume,
cross-revision reuse and all next-checkpoint work are excluded.

The preceding framework candidate passed 44 focused tests, with one expected pending
measurement-artifact skip; the final reviewed seams pass five affected tests.
Compilation, CLI parsing, diff checks and independent source review pass. Fresh
Prepare, Freeze and independent authority review pass. Evidence is under
`build/m1-7/evidence/framework-20260915-120000/`. Contract SHA-256 is
`0c82a7044348193af2d68b25c6645263e15c4f532f4015257324c33227b930c3`.
The preceding authority remains preserved as historical evidence, not authority
for this changed instrument.

**Preceding stop (resolved by R1/R2 above):** the earlier readiness pass accepted
five children / 25 cases, then timed out waiting for Confirm's typed receipt.
Its index and `ready.txt` preserve the failure, with no complete artifact in that
directory. Recovery commit `f1a33a3` remains unchanged. Current full readiness
and the confirmed observer cause are recorded above; quantitative acceptance
remains pending.

**Historical resumption authorization (2026-09-15, completed and superseded):** apply only the reviewed
`System.Action` import relocation within
`tests/plan_review_benchmark.py::_capture_headed_runtime_identity`, from function
entry to the loaded callback. Preserve host initialization, runtime identity
fields, installed isolation and all measurement criteria. Review the exact diff,
compile the runner and retry the existing Freeze stage once, retaining the sole
reviewed smoke. If Freeze succeeds, review authority and continue fixed
measurements; another harness prerequisite blocker requires a stop without
diagnostic expansion. Keep `cf5a00b` unchanged and all subsequent work in separate
commits, following the user's final instruction. Do not split its contents or
add verification merely to reorganize commits. The owning documentation and
genuine authority/measurement artifacts accompany the new work; no product edit
is authorized by this correction.

The import relocation passed exact-diff review and compilation. The single
Freeze retry succeeded and produced `m1_7_plan_authority.json` (49,163 bytes),
SHA-256 `056ebe994473885f541691d00c556ef77a24b603e3b6f703dc70f841572a856b`.
The reviewed smoke and candidate remain unchanged; no second smoke ran.

The scoped fix and authority are committed separately in `30d35f3`, directly
after unchanged `cf5a00b`. Independent authority review passed before the fixed
run. That run stopped at `ui_mutate_plan_selection_click_feedback` with
`selection did not commit a pending frame`. This is a failed correctness
prerequisite, not a measured budget miss or an established product root cause.
No raw artifact, retry, repair, extra diagnostic, validation run or integration
followed. That authority is preserved as historical evidence. The subsequent
review and framework correction above supersede this stop's next-step guidance;
the subsequent R1/R2 repairs and complete readiness above supersede that stop.

**Historical user closure boundary (2026-09-14, superseded):** finish the currently open reviewed
sequential untimed fixture barrier and run exactly one quantitative smoke. If it
passes, freeze inputs, run the fixed measurements and proceed to closure and
verified integration into `milestone1`. If the smoke fails, stop and preserve the
current recovery branch, provide a recap and investigate possible redesign for
review. Do not expand diagnostics. Any unpassed measurement or closing gate
remains a blocker; it cannot be bypassed or relabeled as completion.

`milestone1` remains `40ca76f`; work is on `codex/wip-20260914-1600-m1-7`.
Recovery `cf5a00b` remains unchanged, with scoped fix `30d35f3` and the separate
stop-record commit afterward. Verified
ignored recovery bundles preserve earlier tips. No M1-7 integration or
recovery-branch pruning has occurred.

At the preceding September 14 stop, the sole smoke passed but authority freeze failed at
`_capture_headed_runtime_identity` importing `System` before desktop runtime
initialization. No authority or measurements were produced then.
Independent source review confirms an instrument initialization-order defect:
the passing headed child imports `System.Action` inside the host's loaded callback.
The subsequently authorized correction moves the freeze probe's import into its own loaded
callback, then verifies the existing isolated Freeze command and authority
binding. No direct CLR bootstrap, product change, extra smoke or criteria change
is proposed. The measured source hash must be refreshed before authority creation.
No further diagnostics were added; the September 15 result is recorded above.

Integration is outside the current framework authorization. Preserve the existing
recovery baseline and separate follow-up commits; do not rewrite or split them
to prepare an unsolicited merge. Recovery refs can be removed only after future
verified integration and full accounting. AGENTS safety, recurrence and recovery
rules remain binding; any later integration or checkpoint work requires active
user scope.

## M1-4 delivered

Delivered in `ab453e1` on `milestone1`: process-live blank task creation,
newest-first navigation, reinjection/recovery and explicit closure using the
existing lifecycle, observer and service owners. Terminal release retains the
task; busy close requests cancellation and removes the card only after
settlement and successful close. Failed close remains retryable. Existing
48-task admission and command/receipt/worker bounds remain enforced.

Generation-aware native callback containment prevents obsolete pywebview return
errors after reload while preserving command effects, recovery, current error
visibility and actual worker-exit accounting. This is not an atomic JavaScript
delivery fence; [BRIDGE](BRIDGE.md) and [INTERFACES](INTERFACES.md) own the active
contracts and limitation. Exact test consumers were migrated without filtering
stderr or relaxing their independent assertions.

No Setup/workflow content, durable task survival, domain retry/purge controls,
asynchronous command boundary or new timing/whole-runtime memory acceptance was
delivered in M1-4. Acceptance passed 4,862 ordinary
tests (four existing capability skips), 29 installed headed tests, all 12 import
contracts, documentation checks and independent adversarial review. Detailed
task history is in CHANGELOG; recovery chronology remains in Git history.

## M1-async delivered

Native create/start/release/close now separate admission from bounded completion
through the existing document channel. Ordinary/custom dispatch stays
synchronous. Task/session owners still execute and recover effects; reload
retires delivery without canceling admitted work. One shared 64-exchange budget
retains both actual worker exits and both delivery phases before reuse.
Completions are capped at 65,536 UTF-8 bytes, with a bounded FIFO, readiness
priority and appearance fairness. Browser correlation distinguishes host and
page generations, bounds early delivery, and uses existing recovery after
uncertainty. The atomic native final-epoch/send guard remains intact.

No generic scheduler, cancellation framework, durable command history,
whole-runtime resource certification, retired reservation/lease recipe or
M1-5 location behavior was delivered. Direct-response limits and all M1-4
effect, recovery and lifecycle guarantees remain active. The user-approved
README status update and logging startup-fixture migration are included.

M1-async-G covers the declared transition matrix, four command projections,
replay/timeout/reload, two-worker custody, first-excess population/size refusal,
post-effect delivery failure, saturation cleanup and shutdown recovery. Its
focused, neighborhood, ordinary, installed headed, import and documentation
checks accompany fresh adversarial source/evidence review. BRIDGE and
INTERFACES own the implemented contracts. The checkpoint is delivered by
`feat(web): add bounded asynchronous command completion` on `milestone1`
from `74aa6b7`; Git history identifies the atomic commit.

The preimplementation twelve-selector baseline and pinned runtime/source
receipt remain in `build/m1-async-design/evidence/`. The finite accepted plan,
replay inputs, transition matrix, per-run candidate hashes and raw closure
results remain in ignored `build/m1-async/inputs/` and `evidence/`.
HANDOFF records the final counts and immediate next work. These functional
checks do not change protected measurement authority or close release gates.

## M1-5 delivered

Delivered in `e19ed9d` on `milestone1` after M1-async. Fresh picker-backed
plan starts and inventory/integrity share typed location admission. Inputs
are literal and bounded; current volume identity, remount/clone resolution,
no-follow admission and existing point-of-use re-probes remain effective.
Remembered sources, targets and active pairs derive from durable sync activity,
each limited to five identity-deduplicated results. Remembered hints grant no
authority, and merely selecting or admitting a location writes no recent record.

Task refusal creates no delivery/session effect; equal replay performs no new
native admission. Two introduced service regressions were corrected before
delivery: exception-context retention and oversized input entering task custody.
Preimplementation probes were refreshed on integrated `675181a` before coding.
Closure passed 680 focused, 2,697 neighborhood and 4,912 ordinary tests (four
existing privilege skips), all 29 installed WebView2 tests, twelve import
contracts, documentation checks and independent adversarial review.

No Setup widgets, frozen options, Plan-again UI, schema/index changes, domain
policy changes or new resource certification were delivered. Retired DTO,
reservation and command-count recipes were not revived. Raw evidence remains
under `build/m1-5/evidence/`; later checkpoints implement the remaining user
outcomes through their own accepted gates.

## M1-6 delivery

M1-6 delivers backend-canonical frozen Setup with typed, picker and run-derived
recent folders/pairs; task-local options; standalone inventory; serial
best-effort pair creation; and fresh-identity Plan again in a new task.
Existing task/session owners attach the first session to a blank task and
preserve stable replay, recovery, close and admission bounds. Picker ambiguity
uses the user-approved purpose-bound continuation within the existing slot
population; an explicit current mount is required before Start.

Whole-gesture revisions prevent stale edits from restoring folder authority.
Form and batch starts exclude one another; uncertainty retains the same command
for retry. Per-task readback restores frozen inputs, and plan readiness requires
an actual artifact. Global defaults remain unchanged.

The same checkpoint condenses M1-5's delivered history and records the substantive
transparent-host rendering issue in BUGS without changing its header/policy.
Its cause remains unconfirmed and investigation is deferred indefinitely.
Changes to native Mica/material or global settings, durable tasks, M1-7
review/execution, inventory projections and new resource certification remain
excluded. Retired
command-count, reservation and aggregate-owner-graph recipes remain retired.

M1-6-G verification: 1027 passed, 2 deselected in 28.13s; neighborhood
2731 passed, 2249 deselected in 113.29s (0:01:53); ordinary 4946 passed, 4 skipped, 30 deselected in 212.33s (0:03:32);
installed headed 30 passed, 4950 deselected in 150.10s (0:02:30); all 12 import contracts.
The four ordinary skips are unchanged core/tool symlink cases lacking Windows
privilege (WinError 1314); no M1-6 or bridge gate was skipped. This checkpoint is
not release-wide or compositor-health acceptance. Final independent adversarial
review and documentation/hash checks passed before its atomic commit.

Delivery is one `feat(web): deliver frozen task setup and location flows` commit
on `milestone1`, based on `b98dce4`. The accepted study is retained in
[the archive](obsolete/M1_6_SETUP.md). Exact commands, candidate hashes, raw
results, review dispositions and screenshots are in ignored `build/m1-6/`;
successful gate directories are `focused-final05`, `neighborhood-final04`, `ordinary-final04`, `headed-final03`, `imports-final02`.
No test was retired and no recovery branch or worktree was created.

## Investigation and regression map

The current service rolls `committing` back only when admission fails;
post-admission preflight refusal remains committed. `run_plan` saves a plan
with its review-preflight verdict even when that verdict is negative; a typed
plan-admission limit instead saves no artifact. Existing preflight tests pin
the exact capacity boundary, fresh-world drift, and refusal without plan or
selection mutation. Existing core/planner tests pin operation identities,
selection digests, and dependency closure. Preserve these behavioral witnesses
when implementing fresh Plan again; a digest is not a filesystem snapshot.

The executor already projects generic I/O reasons and accepts `Stop` after
ordinary failure settlement, but its default policy continues non-sharing
failures. M1-8-capacity is a separate reviewable behavior commit before its
frontend consumer. Verify classification through the real error wrapping path,
post-effect and recording outcomes, and the later-operation stop sweep in the
executor runtime/settlement tests, then core/workflow/interface consumers.
Run the ordinary suite and unchanged retained oracle; final review must reject
any new settlement mechanism or capacity label that masks an unrelated failure.
Update EXECUTOR, FEATURES, DESKTOP_UI, and the register with the implemented
boundary and evidence before `feat(executor): stop on recognized capacity failure`.

For test cleanup, retire only unimplemented UI retry/reopening/cleanup promises
from future acceptance lists. Keep direct-service artifact replacement,
admission rollback, protocol replay, close recovery, automatic operation/read
retry, and pause/resume tests. They protect different behavior. Add terminal
action-availability witnesses when each surface activates, including degraded
completion, abnormal termination, and first manual verification. Add trash
location-only and evidence-backed count cases without requiring a full trash
inventory. Green existing tests cannot prove these new frontend outcomes; red
tests justify removal only when their exact retired product promise is named.

All remaining rows are pending product work. The baseline is the implemented
public/CLI, schema/event, authority, and settlement behavior recorded by the
closed reduction registers; those guarantees remain protected. The future
capacity checkpoint changes only the explicitly accepted failure classification
and later-operation admission policy. No implementation recipe from the discarded
compact-plan branch is an additional prerequisite. Product changes follow the
finite rows above, owning subject docs, and AGENTS/DEFENSE stop rules.

## Accepted behavior carried by the delivery rows

Normally completed tasks retain file lists, item statuses, and phase aggregates
for read-only review. Execution-only completion may offer its first eligible
manual verification; linked completion needs no further action. Non-stopping
degradation keeps the normal review experience with visible issues. Canceled or
abnormally terminated sessions retain terminal truth without resume, domain
retry, or session cleanup. Live pause/resume remains separate. Busy task close
requests immediate best-effort cancellation and keeps the card until settlement
and resource release permit closure; close never implies trash purge. Forced
process exit provides no durable task/resume guarantee.

Capacity refusal before execution (including queued wakeup) retains the task
without execution, automatic retry, or automatic close. Scan/planner admission
refusal may have no plan; review preflight can retain an immutable plan with a
negative verdict. Explicit Plan again resolves reviewed location identities,
creates fresh Setup in a new task, scans again, and requires fresh review. It
never copies selection/authorization or changes the old artifact. Disk space
freed by removing source/target entries is accounted for by that fresh scan,
not by assuming that a prior selection digest binds the changed filesystem.

Recognized execution-time disk-capacity failure is the narrow planned addition
above; the current default failure policy continues past non-sharing failures.
Generic I/O already has a typed reason and needs ordinary frontend presentation.
Yellow capacity mapping uses existing DESKTOP_UI semantics and never hides
independent known failures. Trash-location text is accepted for M1; exact
counting is conditional on complete outcome evidence and display placement is
open. No filesystem inventory or purge is added to populate that information.

Location admission is workflow-owned and reused by typed, picker, and recent Setup/inventory inputs. A remembered location is not authorization; every consumer retains its point-of-use re-probe. Setup freezes its semantic plan options in a backend-derived snapshot and never writes global defaults or makes browser text/filter normalization authority.

Plan review must preserve operation, selection, scope, and fresh-preflight truth across view gestures. New views use canonical path-key order; filename, raw size, and raw mtime sorting in either direction and reset to canonical order are accepted M1 behavior. Sorting is process-live view state only and cannot alter selection, commitment, operation/dependency order, risk/counts, or action scope. It orders complete siblings before windowing and preserves node identity/hierarchy. Its exact protocol, validation, and scale evidence belong to BRIDGE and PRESENTATION.

Execution, inventory, and post-copy overlays stay distinct from each other and from ledger-derived state. A zero-byte activity that ran is never presented as unrun. Inventory warnings stay outside path/action scope and publication is complete or retains the prior complete generation. Baseline, verify, and rebaseline remain distinct operations. Rebaseline requires acknowledgement, includes eligible selected null-evidence files, replaces/creates evidence after a fresh hash, clears verification freshness, and does not become compare-and-accept. Manual exact post-copy verification uses an atomic handoff classification, works only on a ready subset, preserves original execution truth, and reports ineligible outcomes truthfully.

Release remains an accepted outcome. [INTERFACES.md](INTERFACES.md#sh-g-release-criteria) owns the open SH-G-15 scoped cold-start and repeated/long-workload resource policy. It has no numeric budget or acceptance artifact yet; runtime request/population bounds and the separate SH-G-8 transport-custody evidence remain unchanged.

## Release completeness

BR-G-43: active docs, README and UI/mockup status must describe shipped behavior.
Map every active DESKTOP_UI acceptance item to its subject check or an explicitly
approved deferral; an omitted item or copied unmapped checklist is not closure.
BR-G-44: from a clean checkout, run the complete suite including ordinary-default
exclusions, lint-imports and diff checks. All test_br_g cases must be collected
and pass without skip/xfail on Windows; narrow selections do not substitute for
release evidence. TESTS owns collection commands and routing. These requirements
remain open release obligations, not an assertion that this checkpoint delivery
performed a product release run.

## Resumption

M1-4, M1-async (`675181a`), M1-5 (`e19ed9d`), GUI-1 (`b98dce4`) and M1-6
are delivered on `milestone1`. M1-7 remains active under its implementation and
user closure boundary above. HANDOFF owns current operational context; AGENTS
owns containment. No later checkpoint, halo workaround, push or PR is authorized.
