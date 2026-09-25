# M1 Delivery Register

This is the sole active M1 delivery register. Subject contracts remain in
[ARCHITECTURE](ARCHITECTURE.md), [DEFENSE](DEFENSE.md), [BRIDGE](BRIDGE.md),
[PRESENTATION](PRESENTATION.md), [INTERFACES](INTERFACES.md),
[DESKTOP_UI](DESKTOP_UI.md), [FEATURES](FEATURES.md) and [TESTS](TESTS.md).
The [archived delivery register](obsolete/M1_8_DELIVERY.md) preserves the finite
R0–R3 criteria, original B1–B6 dispositions and recovery chronology.

## Post-M1-8 reduction plan

### Main objectives

Reduce duplicated presentation and boundary work while preserving reviewed
effects, truthful results and usable desktop flows. Keep useful performance
measurement as optional developer tooling. Make documentation easier to maintain:
one methods/results owner, compact delivered records and small-change workflow
by default. Refactor the existing shell before adding M1-9 consumers; no rewrite.

### Scope and decisions

Planning baseline was `milestone1` at `a7f8402`; execution begins at `6a55239`
after documentation reconciliation and five study moves. Recheck changed seams
before dependent implementation. The
[study](POST_M1_8_ABLATION.md) owns findings, source evidence and compact rejected
dispositions. This section is the sole AB register. The user activated the full
AB-1–AB-10 batch; dependent rows start after their named prerequisites close.
Revision based on `0c74ee7` settles D2/D4 from the user's instructions without executing
AB-7 or changing the current transport contract in BRIDGE.

- In scope: W1–W4 documentation/workflow, E1 optional benchmarks, L1–L4,
  bounded S1/S2/S3, S4 only at the response adoption boundary, T1 and the T2
  removals directly caused by these changes. S3's direction is accepted.
- Preserve ingress, storage and ownership validation, including history write
  admission and readback/hash/column/receipt checks; mutable execution authority,
  workflow policy, atomic effects, settlement, admission bounds, native Advanced
  Color mitigation, accessibility and ordinary observation recovery.
- Exclude L5/L7/L8/L9 (rejected), L6 (unqualified), the S5 owner merger, executor
  continuation/settlement changes, broad projection redesign, M1-9/10 delivery,
  DOC-2 branch rewriting, push/PR, raw-evidence deletion and new speed targets.
  Retain copy metrics and the Plan-again tracer; relocating the latter is allowed
  only with its existing consumers, not as permission to retire it.
- W2 follows the user's decision: default to small change unless asked otherwise.
  Checks/tests/review/documentation and concise changelog remain mandatory as
  applicable; permanent detailed plans/registers are optional unless requested.
  The user owns classification. Explain and ask to escalate/formalize when a
  delivery crosses architectural ownership, public contracts, safety guarantees
  or multiple independently deliverable outcomes. No agent-created eligibility
  rubric, size threshold or automatic register for every audit finding.
- D1 is a design direction, not a demonstrated absence of reload gestures.
  AB-6 must establish unsupported-reload behavior in the installed host.
  D2 is settled: remove page-side elapsed-time deadlines that abandon mutating
  command results or automatically replay mutations. Keep delayed-response
  feedback, bounded observation recovery, authoritative identity, duplicate-effect
  protection and original-outcome retention/recovery. Native delivery can fail
  after an effect; uncertainty does not disappear with reload/deadline removal.
  Failed communication must show an explicit "outcome unavailable" state rather
  than unqualified "working…" indefinitely. Retain startup, shutdown, worker/
  resource and genuinely bounded observation timeouts. AB-7 simplifies existing
  asynchronous admission/completion before considering any new protocol.
  D4 is settled: retain highlighting/focus and its separation from execution
  checkboxes without feature reduction. D6's missing-row acknowledge/restore UI
  needs explicit allocation when M1-9/10 is activated, not deletion as dead code.
- E1 loses automatic latency/empirical-memory gating for the named performance
  families. That is an intentional acceptance-policy change, not proof of zero
  performance risk. Keep enforced bounds, meaningful counted-work regressions,
  SH-G-15 release resource/leak checks, transport security/custody and the executor
  settlement oracle. Benchmark failure must remain visible and truthful.

The preserved baseline is behavioral, not the number or literal text of tests.
Recorded MOVE-1 evidence has 5,417 ordinary passes/five environment skips and
12 imports; M1-8 records 33 installed obligations. These are historical receipts,
not a fresh run of this plan. Characterize affected seams before editing and run
the commands below after changes. Red tests may assert deliberately removed
mechanisms; green tests are insufficient to prove no regression. Classify every
changed/deleted detector by its retained guarantee or explicitly retired outcome.
Do not weaken a detector of an unchanged guarantee to make the suite pass.

### Investigation and regression map

| Risk / actual seam and consumers | Failure to guard against | Owning checkpoint and detector |
| --- | --- | --- |
| Active docs and five archived studies; M1_PLAN completed rows, DOC-2, M1-9/10/12/Release | Condensation loses a binding decision, turns an unfinished item into a pass, or leaves contradictory policy | AB-1: source-to-owner accounting, incoming links and pending-row comparison; AB-10 whole-doc sweep |
| `tests/plan_review_benchmark.py`, M1-8 receipt/UI adapters, `_plan_review_scale.py`, related validators/probes; setup/task-shell headed children also import helpers | Moving drivers breaks functional fixtures or installed observations; deleting certification removes actual behavior detectors | AB-2: import/caller inventory, independent fixture/action checks, driver failure tests, ordinary and installed suites |
| `tests/bridge_event_benchmark.py`, child/retained-memory helpers, `tests/history_benchmark.py`; executor/verifier tools already in `tools/` | Optional timing demotion accidentally removes custody, release resource or history correctness checks | AB-2: classify by consequence, preserve those gates, move driver ownership without automatic demotion of unrelated claims |
| `db/repositories.py` unused mapping API vs live `find_current_mapping`; planner/workflow consumers | Delete live correspondence or revive retained-alias rejection | AB-3: all caller search plus MOVE-1 repository/planner/workflow behavior |
| Service `_resolve_plan_selection_ids`, `_selection_preview_locked`, task port and drain `open_plan_view`; CLI/API public preview | Full preview allocation remains; torn revision/membership transfer, altered dependency closure or stale execution intent | AB-4: exact current/stale capture, folder/leaf/empty/mixed selection, public preview compatibility, 120k counted-work witness |
| Bridge response capture/validation/projection and longest drain-prefix admission; page decoder | Aliasing after adoption, cycle/unsafe type acceptance, wrong byte limit, task mismatch or lost custody on failure | AB-5: existing boundary/custody cases, mutation-after-capture and exact-limit cases; AB-8 page identity adoption |
| Host document generations; `commands.py::CommandSpec`, `bridge.py` asynchronous admission/completion, `document_channel.py::DocumentChannel`, `bridge.js`/`app.js` attempts and lifecycle receipts | Late retired-page callback gains authority; elapsed time abandons a recoverable result or duplicates an effect; native delivery fails after mutation; observation exhaustion hides uncertainty; close drops live ownership | AB-6/7: installed gestures, delayed/duplicate returns, post-effect delivery failure, bounded observation exhaustion/late recovery and close races; preserve task-lifecycle concurrency tests |
| Event bus Gap → SessionObserver → drain `_TaskState` → JS reducers → shell controls/windows/details | Removing browser reduction fabricates completeness, loses terminal axes, misroutes task state, rounds large integers or drops control/Close feedback | AB-8: real producer→snapshot→page scenarios, bounded windows/one detail, navigation and deferred-response probes plus installed journeys |
| Static CSS/source pins, design tokens and gallery | Removing a spelling assertion also removes focus, reduced-motion, forced-color or safe-sink detection | AB-9: retained semantic/computed-style/native witnesses; no whole-cohort deletion |

### Checkpoint register

Dependencies are minimum prerequisites. Execute in the listed order by default;
independent rows can be reordered when ready. Each row has one coherent
commit. Shared test retirement travels with its owning behavior, not in a later
cleanup commit. New findings do not silently add rows.

| ID | Accepted outcome | Depends on | Primary verification | Status |
| --- | --- | --- | --- | --- |
| AB-1 | Documentation/workflow ownership is clear; delivered records compact; PERFORMANCE established | Active batch | 320 links; independently extracted figures; A6 receipt/tree verification; diff and independent review with corrections | Complete in `29d9b8f` |
| AB-2 | Optional, usable performance drivers live in tools with required correctness/release checks preserved | AB-1 | 5,302 ordinary, 33 installed, 12 import passes; selected drivers, preserved evidence and independent review | Complete in this checkpoint commit |
| AB-3 | Unused database mapping API removed without changing current correspondence | AB-1 | Database/planner/workflow neighborhood and caller closure | Reviewed as `c5f1de8` in isolated worktree; awaiting integration after AB-2 |
| AB-4 | Desktop selection capture avoids redundant work with one revision-bound handoff | AB-2 | Selection/service/task-port consumers, counted work and installed Plan | Pending |
| AB-5 | Bridge response adoption consolidates repeated traversal without weakening boundaries | AB-2 | Response/custody/decoder consumers, ordinary and installed transport | Pending |
| AB-6 | Unsupported reload has one contained restart behavior instead of reinjection recovery | AB-2 | Host/transport/lifecycle races and installed gestures | Pending |
| AB-7 | Existing admission/completion preserves original outcomes without page-timeout result abandonment or replay | AB-6; D2 settled | Delayed/post-effect failed delivery, bounded observation recovery/exhaustion, duplicate protection and close | Pending |
| AB-8 | Existing shell renders bounded authoritative Python task snapshots | AB-4/5/6/7 | Producer→snapshot→page, ordinary/imports and installed task journeys | Pending |
| AB-9 | Remaining visual/source pins protect behavior rather than incidental spelling | AB-8 | Static/security, computed style, ordinary and installed gallery | Pending |
| AB-10 | Integrated reductions preserve the complete retained workflow and have coherent docs/evidence | All above | Overall final sweep below | Pending |

### Detailed checkpoints

#### AB-1 — Documentation first

**Objective.** Establish the documentation and workflow rules before moving
machinery or changing acceptance. Merge W1/W2/W4 and the remaining W3 accounting
because they deliver one consistent set of owners and recording rules.

**Scope and approach.** Edit AGENTS, ARCHITECTURE, DEFENSE ownership routing,
TOOLS, TESTS routing, README, M1_PLAN, PRESENTATION, relevant BRIDGE/INTERFACES
links, the study, CHANGELOG and HANDOFF; create `docs/PERFORMANCE.md`. Audit
FEATURES only for duplicated implementation prescriptions touched by this pass.
HISTORY is a direct profile/method-link consumer and receives a narrow routing
edit. The finite AB-1 population is these documents and their incoming links;
no product, tests, tools, or evidence JSON change. The commit boundary is this
single documentation ownership and delivered-record compaction outcome.
Make W2 durable exactly as above, retaining safety, recovery and recurrence stops.
Keep component mechanisms that enforce guarantees; remove duplicated procedure,
not ownership or safety. No product/test/tool edits or benchmark demotion yet.

PERFORMANCE owns measurement methods, fixture/profile/scaling, aggregation,
provenance, commands and result tables across presentation, bridge, history,
executor/verifier and release resource observations. Component docs retain
contracts/decisions and link to methods; DEFENSE owns consequence/authority,
INTERFACES retains release acceptance, TOOLS owns tool structure/invocation.
Move PRESENTATION's procedures and observations, leaving its bounded-work,
selection, identity and view contracts. Carry current gate classifications
unchanged until AB-2: no period with a supposedly optional test still enforcing
a mandatory performance certificate. Label the planned transition explicitly.

Define `tools/performance/` before creating it in AB-2: family-named drivers,
small shared fixtures/runner helpers only when actually shared, assets beside
their driver, tests under `tests/`, output under ignored `build/`. Existing
executor/verifier tools need no gratuitous relocation. No new framework or
parallel permanent evidence register.

Compact completed M1-4–8, M1-async, GUI, MOVE-1, GUI-W1/WR1 and PA records into
rows containing delivered outcome, current owner and history/evidence pointer.
Preserve pending DOC-2, future product/release rows and binding decisions;
confirm the M1-8 integration receipt before labeling A6 closed. Existing Git,
CHANGELOG and archived delivery docs hold chronology; do not create a new archive
for every small fix. W3's five moves are already done: verify, do not redo them.

**Acceptance criteria.** One current owner per rule; all pending decisions
survive; zero new broken links; no rejected item disappears; no measurements
presented as new observations or current guarantees. PERFORMANCE includes a
source-linked table with revision/profile, fixture, statistic/unit, sample count
and limitations. At minimum extract compact Plan cold base/info-heavy, unchanged
window and memory-overlap observations, plus latest M1-8 click/receipt results.
Use `tests/interfaces/web/m1_7_plan_compact_measurements.json` and its compact
contract/authority, plus `m1_8_execution_ui_{receipts,result,authority}.json` in
the same directory and their declared compact authority. Preserve the distinction
between a recorded source binding and verification against today's checkout.
Source inspection found Plan maxima 1,752.5309/2,764.6222 ms (five cold children
each), unchanged-window max 1.6856 ms (30 samples), overlap 280,768,512 bytes
(five samples), and U-v2 worst click max 20.3 ms, worst receipt p95 72.0 ms/max
73.3 ms. Recompute from committed JSON before publication; do not compare unlike
endpoints or merge maxima/p95 across families into one score.

**Regression watchlist.** Lost historical safety disposition; stale anchor;
W2 replaced by another agent rubric; an empirical target silently becomes a
production bound; pure documentation relocation accidentally retires a gate.

**Tests and evidence.** Diff/relative-link/anchor checks on changed docs and
incoming consumers; compare every old pending row and guarantee to its new
owner; independently derive table values from JSON. Record checks in the existing
ignored study directory. Product tests are not required for this ownership-only
pass; any executable test-authority change belongs to AB-2.

**Documentation and handoff.** Record the AB-1 owner map, extracted sources and
AB-2 transition state once; shorten HANDOFF to immediate resumption needs.
**Adversarial review.** Inspect the actual removed paragraphs and every retained
pending/accepted item, rather than judging the new document in isolation.
**Commit gate.** All above verified; `docs: simplify delivery records and centralize performance methods`.

#### AB-2 — Performance tools and optional benchmarks

**Objective.** Separate performance exploration from ordinary acceptance without
losing useful drivers or correctness checks. Policy, driver movement and direct
consumer changes form one atomic migration; a move-only commit would preserve
the expensive coupling and invalidate old source certificates unnecessarily.

**Activated population at `29d9b8f` (2026-09-25).** Tool producers are the five
`tests/{plan_review,m1_8_execution_receipt,m1_8_execution_ui,bridge_event,history}_benchmark.py`
drivers, the dedicated bridge child/page assets, the M1-8 UI probe,
and the existing `tools/__main__.py` command router. Direct consumers are the
three `tests/interfaces/web/test_*_scale.py` modules and their three private
validators, `test_bridge_event_benchmark.py`, `test_headed_evidence.py`,
`tests/_departments.py`, and shared headed helper imports. The bridge retained-state
sizer stays byte-identical at its current test path because frozen SH-G-8 custody
imports and hashes it; the moved driver uses that helper through an explicit path.
Setup/task-shell headed
children and tests are regression consumers; they do not import these benchmark
drivers. `tools/performance/` owns selected-case drivers and their dedicated
assets; `tests/` retains independent fixture, action, failure and counted-work
assertions. Documentation population is DEFENSE, PERFORMANCE, BRIDGE,
PRESENTATION, HISTORY, TESTS, TOOLS, this register, CHANGELOG and HANDOFF, plus
README only if its phase synopsis changes. Historical JSON/contract/authority
files remain byte-identical in `tests/interfaces/web/`.

Preserve real installed endpoints, exact fixture/action witnesses, bounded child
and Job cleanup, truthful incomplete output, runtime/revision provenance,
database readback and release limits, frozen SH-G-8 custody, SH-G-15 and executor
settlement. Demote only Plan/UI latency and empirical representation memory;
retire their active readiness/index/hash/legacy certificates with their callers.
No product/protocol change, tracer retirement, broad helper relocation, new speed
target or replacement evidence framework belongs to AB-2. The existing bridge
diagnostic's unassigned v5 migration is not implied by moving it. A required
protocol repair changes scope; a truthful failed smoke alone does not block
independent migration. One reviewed commit includes tools, consumers and policy.
Gate: focused live fixture/action and failure controls; selected Plan, installed
UI receipt, bridge launch and bounded history smokes; tools/interfaces/database,
ordinary and installed interface suites; import law; unchanged historical JSON
hashes; final adversarial source/evidence review. Stop on any repository mandatory
consequence or a mechanism/safety boundary change.

**Implemented.** `python -m tools performance --list` exposes
Plan component, installed execution-receipt/UI, bridge-event and history cases;
selected runs write one report and raw child evidence under the caller's named
output. The five drivers, bridge child/page assets and UI probe now live in
`tools/performance/`. Three Plan/receipt/UI benchmark scripts, three private
certification validators and the old UI probe were retired with their direct
callers; the three collected test modules retain independent fixture/action,
failure and current rootless-view assertions. Setup/task-shell children and
shared headed helpers were inspected as regression consumers. Tools use the
uncollected native helper, not collected test modules; the frozen SH-G-8 sizer
remains at its custody path. The bridge case labels archived-HEAD product and
working-tree driver source separately. Retained history release checks remain
in its selected `release` case; the small `smoke` case does not close them.

The 22 Plan component IDs underwent a finite result-kind and current-fixture
audit. Twenty-one non-memory cases matched after explicit rootless adaptation
of unchanged-window total, hostile-search row count and the visible-folder
collapse action; the memory case matched after rootless base/staged window
totals and retained-byte sample-kind correction. The frozen contract and raw
JSON remain unchanged. Installed receipt cases and execution UI cases reuse
the current rootless view adapter and include resolved installed package path
and version in child observations. A selected real installed receipt case
completed with six exact samples and a released session; the earlier sandboxed
attempt timed out with bounded Job cleanup and remains incomplete evidence.
Bridge native timeout remains an unknown-cause diagnostic, not a claimed v5
repair. The finite retirement and evidence dispositions are in ignored
`build/post-m1-8-ablation-20260925/ab2-migration.md`.

Activate E1 atomically in DEFENSE, PERFORMANCE, affected BRIDGE/PRESENTATION
criteria, TESTS/TOOLS and callers: Plan/UI latency and empirical representation
memory are advisory. Retire only their readiness certificates, partial-index
acceptance, source-hash requalification and active legacy-validator replay.
Keep independent fixture/action checks, bounded child execution/cleanup, truthful
incomplete output and runtime/revision provenance. Classify bridge-event/history
release/resource/correctness clauses individually: moving a driver alone does
not demote unrelated release or safety acceptance. Keep SH-G-15, transport custody,
settlement and enforced limits. No tracer retirement, speed target or new receipt
framework. Existing raw JSON/contract/authority files remain byte-identical at
their current paths, even when code moves; old interpreters remain recoverable
from their recorded Git revisions.

**Acceptance criteria.** Ordinary pytest invokes no demoted benchmark collection
and requires no current performance certificate. Explicit tools commands run
selected cases, report all samples and environment, distinguish failed/incomplete
measurement from slow results, and clean up children. Required correctness,
counted scaling, release and security tests remain discoverable. No accidental
import/path dependency on a retired driver or changed archived JSON. A slow valid
sample is advisory; an invalid fixture/action or failed child is a tool failure.

**Regression watchlist.** Wrong installed endpoint, fabricated fixture totals,
mixed before/after profiles, setup/task-shell regressions, leaked children,
overwritten evidence, hidden failure, lost history write/readback checks.
**Tests and evidence.** Characterize fixture manifests/expected orders and actual
action completion before movement. Run retained/revised scale, benchmark and
headed-helper controls, `--dept tools --dept interfaces --dept database`, ordinary
pytest and imports; run installed interface suite for shared native helpers.
Smoke one component case, one installed UI receipt case, bridge-event launch and
history driver with a bounded fixture; exercise failed child and incomplete output.
These prove tool operability, not timing acceptance; no full historical benchmark
collection is required merely to move code. Check archived JSON hashes unchanged.

**Documentation and handoff.** PERFORMANCE gives exact implemented commands,
retained case map and active/advisory classifications; TOOLS/TESTS give routing.
Keep raw build evidence in place. Committed JSON embeds samples and provenance
adequate for numeric summaries, but hashes cannot recreate missing wheels,
screenshots or failure logs. Record those limitations and recommend a durable
external archive for irreplaceable material before future cleanup. No raw move,
deletion, Git binary import or new archive service in this checkpoint.
**Adversarial review.** Trace each removed validator to its consequence and
consumer; verify a failed endpoint cannot yield a fast successful report and
functional tests still work without historical acceptance machinery.
**Commit gate.** Policy/code/consumers/docs pass together;
`refactor(tools): make performance measurements optional developer commands`.

#### AB-3 — Remove unused mapping lookup

**Objective.** Remove L1 independently of UI work.
**Scope and approach.** `db/repositories.py::find_mapping`,
`get_mapping_snapshot`, `_disqualified_identities` and proven exclusive test/doc
consumers. Search all callers before deletion; keep live `find_current_mapping`,
current scan/link policy, ledger/history and SQL schema unchanged.
**Acceptance criteria.** No remaining supported caller requires the deleted API;
repeated native move/no-op behavior and genuine hardlink refusal still hold.
**Regression watchlist.** Shared query helper removal, stale-alias semantics
leaking back into planner eligibility; detect in MOVE-1 cases.
**Tests and evidence.** Characterize relevant repository cases, then database,
planner and workflows departments; existing native move regression and imports.
Search source/tests/tools for removed names; classify obsolete API tests.
**Documentation and handoff.** DATABASE/PLANNER only where descriptions change,
CHANGELOG and compact AB status; no new substantive bug claimed.
**Adversarial review.** Verify the deleted path is actually unused and the current
mapping query and general conservative inspection retain their distinct roles.
**Commit gate.** Focused/neighborhood/import/doc checks pass;
`refactor(database): remove unused historical mapping lookup`.

#### AB-4 — Selection handoff without redundant construction

**Objective.** Merge L2/L3 as one change to desktop selection capture, avoiding
full public preview construction and unnecessary folder-wide work.
**Scope and approach.** Service resolver/preview, `task_port.py`, drain
`open_plan_view` and direct consumers. Derive toggleable membership lazily for
folder resolution. Add the smallest internal detached handoff of artifact/plan
identity, revision, summary and membership captured consistently under the
existing owner. Keep public CLI/API preview and workflow mutation authority;
no cache framework, projection topology change or bypass flag.
**Acceptance criteria.** Desktop view-open no longer materializes per-operation
public views solely for summary; membership and revision cannot be torn. Leaf
selection avoids unrelated folder derivation. Selection closure, hidden choices,
highlight/checkbox separation, confirmation and stale refusal are unchanged.
**Regression watchlist.** Concurrent commit/retirement, empty selection, folder
own operation vs descendants, stale Plan-again, copied mutable membership.
**Tests and evidence.** Service/task-lifecycle, bridge selection, drain and
plan-review cases before/after; interfaces/workflows departments, ordinary and
imports; installed Plan selection/execute flow. Retain 120k scoped/highlighted
counted-work cases with independent membership expectations. Optional timing
may inform further work but is not a gate.
**Documentation and handoff.** INTERFACES/BRIDGE internal handoff and PRESENTATION
selection decisions; public preview remains documented accurately.
**Adversarial review.** Trace revision and membership from the same owner through
execution commitment and refusal; ensure allocation savings are real in source.
**Commit gate.** One coherent service/adapter change with consumers passing;
`refactor(interfaces): capture desktop selection without full public previews`.

#### AB-5 — Consolidate response adoption

**Objective.** Implement only qualified S4/L4 duplication at one ownership seam.
**Scope and approach.** `web/bridge.py` capture, validation, primitive projection
and drain-prefix helpers plus actual decoder consumers. Document value ownership
before/after each walk; combine only passes over the same detached value. Keep
bounded construction, approved types, scalar fidelity, cycle refusal, canonical
byte calculation, longest admitted prefix and failure cleanup. One pass is not
an acceptance criterion. No generic trusted-value protocol or history/core/
ExecutionSet validation removal.
**Acceptance criteria.** Existing valid wire values and malformed refusals remain
equivalent; caller mutation after capture cannot change a response. Exact boundary
and prefix admission work without unbounded preconstruction. Error paths release
custody and reject mismatched task/session identities.
**Regression watchlist.** Shared aliases vs cycles, large ints, non-finite numbers,
hostile display strings, oversized first item, empty drain and mid-prefix failure.
**Tests and evidence.** Existing bridge response, transport-custody and JS decoder
cases, plus missing alias/limit cases only where needed; interfaces/database/
workflows neighborhood, ordinary/imports and installed transport. Retain history
write/readback and workflow authority purpose unchanged.
**Documentation and handoff.** BRIDGE boundary/source locator, ARCHITECTURE only
if the locator changes; record removed walks and surviving checks in CHANGELOG.
**Adversarial review.** Try mutable collaborator values and malformed types at
every adoption point; verify the optimization did not merely skip validation.
**Commit gate.** Boundary equivalence and all consumers pass;
`refactor(web): consolidate detached response validation and projection`.

#### AB-6 — One unsupported-reload path

**Objective.** Retire reinjection recovery while preserving document containment.
**Scope and approach.** Host/bootstrap generation users, bridge/drain adoption,
app state and relevant probes. Verify F5, Ctrl+R, Alt+Left, mouse Back and context
menu in the installed build first. Keep startup, navigation/origin guards,
shutdown and retired-document rejection. On unexpected second load, revoke that
document's command authority and give an actionable restart path; do not cancel
or release an admitted operation prematurely. Map real remaining generation uses
before consolidation. No renderer-crash recovery claim or S5 lock merger.
**Acceptance criteria.** Reload is not offered as a supported action; an unexpected
load cannot submit effects or adopt stale callbacks. Current tasks finish/settle
safely; normal navigation and observation retry still work.
**Regression watchlist.** Late native returns, startup vs second load, close during
execution, retirement releasing resources while workers are active.
**Tests and evidence.** Host/bootstrap/bridge/drain/lifecycle tests; interfaces
department, ordinary/imports and installed gestures during idle and active tasks,
followed by clean close. Delete only reinjection-specific expectations with their
mechanism, retain security/cleanup cases from the same modules.
**Documentation and handoff.** INTERFACES/BRIDGE/FEATURES and M1-12's reinjection
wording move together; state exact restart behavior and remaining limitations.
**Adversarial review.** Verify disabling gestures did not substitute for actual
stale-document containment; examine native callback and shutdown races.
**Commit gate.** Supported flows and unexpected-load containment pass;
`refactor(web): replace reload recovery with contained restart behavior`.

#### AB-7 — Simplify existing command completion and recovery

**Objective.** Apply settled D2: elapsed time alone neither abandons a mutating
command's result nor automatically replays its mutation. Preserve recovery of
the original outcome when local communication genuinely fails.
**Scope and approach.** Start with the delivered M1-async path:
`commands.py::CommandSpec`, asynchronous admission/completion in `bridge.py`,
`document_channel.py::DocumentChannel`, browser correlation in `bridge.js`,
app attempt handling and existing task/session effect receipts. Several commands
already return admission separately from completion; exploit and simplify that
machinery. Keep direct commands direct unless a specific existing-path change is
needed. No replacement command system, parallel admission/result protocol,
generic scheduler or durable command history is in scope.

Before edits, map each affected mutating wrapper, including direct mutations,
to its current identity, result owner, completion delivery and recovery path.
Remove page-side elapsed-time abandonment and mutation replay triggered by those
deadlines. Delays
may trigger qualified feedback and bounded observation checks; preserve genuinely
bounded observation, startup, shutdown and worker/resource-containment deadlines.
Retain bounded original-result/effect receipts and duplicate protection. Separate
delivery acknowledgment/cleanup from effect truth: an observation timeout or
native post failure must not erase the authoritative outcome, cancel admitted
work or authorize another effect. Reuse task/session reconstruction and existing
result recovery before adding a mechanism. Document retained-result lifetime and
safe retirement without unbounded pending entries or indefinite receipt storage.

**Acceptance criteria.** A result delayed beyond former page deadlines remains
recoverable/adoptable while its identity and ownership are valid, with no timed
mutation replay. Duplicate gestures/late returns produce at most one effect.
Failure after an effect recovers that original result when available; failed or
exhausted bounded observation explicitly reports "outcome unavailable", never
false failure/success or unqualified "working…" indefinitely. Observation retry
does not restart the mutation. Unavailability is a communication fact, not a
terminal operation verdict; later valid observation may resolve it. Pending Close
retains truthful settlement/availability feedback and actual worker custody.
CLI behavior, admission rollback, bounded resources and current process-lifetime
recovery limitations remain; no guaranteed recovery after process loss is added.

**Regression watchlist.** Result eviction on page timeout, conflating failed
delivery with failed effect, retained result lost during acknowledgment cleanup,
observation retry becoming mutation replay, close/start races, unbounded recovery
loops, double confirmation and stale task navigation.
**Tests and evidence.** Characterize current async/direct wrappers and existing
post-effect delivery-failure cases first. Test delay beyond former deadlines,
lost admission/completion delivery after exactly one effect, duplicate/late
returns, original-result recovery, bounded observation exhaustion, later valid
observation after unavailable, and Close/shutdown with a worker still active.
Use controlled clocks/delivery faults; retain startup/cleanup/worker timeout and
capacity tests. Run command/lifecycle/transport cases, interfaces/workflows
neighborhood, ordinary/imports and installed submit/control/close/reobserve flows.
**Documentation and handoff.** BRIDGE/INTERFACES own revised transitions, original
result retention/retirement, observation attempt bounds and unavailable feedback.
Record reuse of existing admission/completion and any removed retry paths; do not
claim that reload removal eliminates uncertain outcomes. AB-8 consumes this path.
**Adversarial review.** Follow an effect that succeeds just before native delivery
fails and an observation budget that expires before a late completion. Prove no
duplicate effect, erased result, false terminal claim or unbounded wait/retention.
If a new protocol proves necessary, explain the architectural boundary and return
for scope adjudication rather than enlarging AB-7 implicitly.
**Commit gate.** All retained failure/lifecycle paths and consumers pass;
`refactor(web): simplify command completion without timed mutation replay`.

#### AB-8 — Authoritative task snapshots and bounded shell refactor

**Objective.** Implement S3 before inventory extends the same shell, removing the
second semantic event interpreter while retaining existing user workflows.
**Scope and approach.** Python adapter task state in drain owns presentation
reduction fed by SessionObserver; workflows still own domain truth and dispatcher
stays domain-blind. Publish detached task/session-bound revisioned snapshots of
terminal/recording axes, progress and unavailable/incomplete facts. Keep bounded
item windows and one-detail reads separate. Define/validate the internal wire
version at browser ingress; do not expose the whole outcome map. Move semantic
event/attempt reduction out of `bridge.js`, `app.js` and `task_status.js`, keeping
drafts, focus, scroll, pending feedback and visual formatting local. Prefer one
Python rate/ETA sample history with monotonic time and explicit reset on attempt/
Gap; the browser only formats the result. Existing panels/renderers remain.
Complete AB-7 before freezing the snapshot shape; snapshots preserve its explicit
outcome-unavailable and original-result recovery states. No framework, preparatory
shell rewrite or S5 merger. D4's highlighting/focus behavior remains intact.

**Acceptance criteria.** Atomic snapshot adoption rejects stale/foreign identity
and preserves exact scalar values. Upstream Gap remains unknown until supported
reconciliation; terminal cannot fabricate item completeness. One semantic progress
owner; controls/follow/window invalidation/Retry/pending Close still work. CLI and
history events and mutable execution authority remain unchanged. Retirement frees
presentation state without changing task/session effect ownership.
**Regression watchlist.** Deferred directory work, repeated attempts, zero/unrun/
canceled/degraded outcomes, capacity plus independent failure, large-byte counts,
Gap immediately before terminal, stale snapshot after navigation or close.
**Tests and evidence.** Characterize current producer→page cases first; test new
Python snapshots from real events and page adoption with the same independent
expected facts. Retain transport/control/cleanup in drain/task-shell JS probes.
Run interfaces/workflows/dispatcher departments, ordinary/imports and complete
installed task/Plan/execution/detail/Retry/Close journeys. Count bounded publication
and window/detail populations at existing large fixtures; optional benchmarks
can compare the updated real endpoints without certifying speed.
**Documentation and handoff.** BRIDGE wire/adoption, INTERFACES state/ownership,
PRESENTATION semantics, ARCHITECTURE locator and PERFORMANCE changed endpoints.
Review tracer usefulness and remaining S5 joins read-only; neither finding adds
implementation. T2 removes only superseded event/reload assertions.
**Adversarial review.** Follow a dropped upstream event, delayed old snapshot,
terminal with missing details and close race end-to-end. Confirm fewer semantic
owners rather than the old reducer hidden behind a new DTO.
**Commit gate.** One server/page protocol change including probes, docs and
installed verification; `refactor(web): render authoritative task snapshots`.

#### AB-9 — Retain behavioral visual tests

**Objective.** Complete T1 on the surviving shell, independent of runtime changes.
**Scope and approach.** `test_frontend_static.py`, `test_design_tokens.py`,
gallery exact-matrix assertions and directly affected assets/helpers. For each
literal/CSS/source-count pin, retain it if it protects a real boundary or replace
its incidental mechanism with an existing behavioral/computed-style witness.
Delete obsolete spelling pins without recreating them under another name. Keep
safe-sink/security bans, keyboard focus, reduced motion, forced colors, selection
and native input detectors. No cosmetic product edits or generic fake DOM.
**Acceptance criteria.** Permitted CSS/refactoring changes no longer fail solely
for source spelling; named visual/accessibility/security guarantees remain tested.
**Regression watchlist.** A single assertion may mix style and semantics; no
whole-gallery/module deletion or loss of native minimum-window coverage.
**Tests and evidence.** Inspect current assertion→guarantee mapping; run affected
modules/probes, interfaces department, ordinary and installed gallery at existing
sizes. For changed detectors demonstrate the targeted violation is caught using
a reversible local perturbation where practical; avoid a new mutation framework.
**Documentation and handoff.** TESTS/DESKTOP_UI only for changed detector policy;
CHANGELOG gives removed incidental pins and preserved guarantees, not a line goal.
**Adversarial review.** Search deleted assertions for semantic/accessibility
obligations with no remaining detector and inspect actual rendered evidence.
**Commit gate.** Retained behavior observed and no product change;
`test(web): replace incidental visual pins with behavioral checks`.

#### AB-10 — Integrated closeout

**Objective.** Verify interactions across the completed reductions.
**Scope and approach.** Complete diff and preserved workflow; verification/docs
only unless correcting an introduced in-scope regression in its coherent owner
commit. No opportunistic implementation from deferred findings.
**Acceptance criteria.** The final sweep below is complete and every row has a
passing gate or explicit user disposition; no unresolved lost guarantee is hidden
by a removed test. A new independent outcome requires adjudication.
**Regression watchlist.** Tool relocation obscures stale endpoints; removed
replay plus snapshot retention loses result recovery; documentation contradicts
actual release checks; archived evidence is overwritten.
**Tests and evidence.** Use final-sweep commands and cross-boundary journeys below;
reuse still-valid checkpoint evidence only where dependencies are unchanged.
**Documentation and handoff.** Compact completed AB rows, preserve rejected/
deferred decisions, list remaining M1-9/10 allocation and DOC-2 decision; D2/D4
are settled retained behavior, not unresolved choices.
**Adversarial review.** Review complete product/test/tool/doc delta and actual
user journey, with evidence for each regression-map row and changed detector.
**Commit gate.** All sweep evidence accounted and working tree coherent;
`docs: close post-M1-8 reduction verification` (only if closeout changes docs).

### Overall final sweep

Established PowerShell verification from repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest -q --dept interfaces -o "addopts=" -m headed
.\.venv\Scripts\lint-imports.exe
git diff --check
```

Checkpoint neighborhoods use `-m pytest -q --dept NAME` with repeated department
options as named above, without an explicit file filter that would hide other
consumers. Focused paths come from the regression map and source inventory.
Ordinary and installed suites must pass under the post-AB-2 classification;
explain every skip and newly removed detector. Existing TESTS probe containment
applies. Do not run historical acceptance merely to recreate obsolete test counts.

Exercise installed Setup→Plan→selection→confirmation→execute→terminal/details,
Plan-again, pause/resume/cancel, navigation, observation retry, pending Close,
unsupported reload and shutdown, including refused/degraded/capacity cases,
post-effect delivery failure, bounded observation exhaustion and later recovery
of the original result without repeated mutation. Retain D4 highlight/focus and
checkbox separation in keyboard, range and hidden-selection journeys.
Verify security/parser rejection, exact identities/scalars, immutable adoption,
bounded ingress/window/detail work and release truth. Retain history write/read
and CLI compatibility coverage from the ordinary suite. Check optional tools use
the final real endpoints, list/run selected cases and report failure honestly;
timing/memory observations are advisory and do not replace bounds or release gates.

Overall completion evidence: command results with source revision and meaningful
failure/skip explanations; installed observations; regression-map dispositions;
independent expected-value/action checks for moved fixtures; unchanged historical
JSON comparison; active/incoming documentation links and final diff review.
Recheck SH-G-15/security/settlement policy consumers for accidental demotion; run
any actually affected retained gate, not every unaffected historical gate.
No unsupported speed or memory improvement claim. Resolve introduced regressions
before closeout; unsupported pre-existing leads remain explicitly deferred.

### Resumption block

- Current checkpoint: AB-1/AB-2 complete; the full AB batch is active;
  remaining rows await their named dependencies, not repeated activation.
- Existing evidence: `build/post-m1-8-ablation-20260925/` contains the study,
  AB-1 checks and AB-2 migration map, selected reports, raw failed child logs,
  focused results, `ab2-ordinary.log/xml`, `ab2-raw-json-verification.json`
  and history/bridge lane receipts. Five archived studies are accounted in the
  current study §13.
- AB-1 verification: `ab1-checks.json` and `ab1-review.md` in that evidence root
  record documentation-only scope, 320 links, source figures, matching A6 trees
  and independent review/correction. No product tests are an AB-1 gate.
- Next action: integrate reviewed AB-3 commit `c5f1de8`, then refresh AB-4's
  prepared design against the integrated tree. The frozen AB-2 tool/consumer source
  passed 95 focused tests, 5,302 ordinary tests (four skipped, 33 deselected),
  33 installed interface tests, 12 import checks, 233 active/incoming links,
  independent review and selected installed receipt/UI
  cases. A later test-only stronger exact COPY-ID assertion passed its focused
  rerun; unaffected ordinary evidence remains valid by dependency. Historical
  bytes were checked in `ab2-raw-json-verification.json`. A product or test
  correction invalidates its dependent gate evidence.
- Current AB-1 documentation check:
  `.\.venv\Scripts\python.exe build\post-m1-8-ablation-20260925\scripts\ab1_checks.py`.
  It checks source-linked figures, integration identity, changed/incoming links,
  diff hygiene and the documentation-only path population. It is task-scoped,
  not a permanent product gate or a substitute for adversarial review.
- Decisions: D2 settled; AB-7 simplifies existing admission/completion while
  retaining original-outcome recovery and explicit unavailability. D4 retained
  without feature reduction. D6 scheduled allocation later, S5/L6/tracer
  retirement deferred. Rejected L5/L7/L8/L9 stay in the study's compact table.
- Preserve all raw JSON, existing build evidence, unrelated work, branch refs and
  stashes. No DOC-2 operations, push or PR. Commit only verified task-owned
  tools, tests and matching docs.
- Stop for AGENTS mandatory safety conditions, changed accepted outcome/ownership/
  safety boundary, or recurrence thresholds. Investigate finite affected consumers
  before proposing escalation; do not silently grow this register. A red test of
  a retired mechanism alone is not a safety stop, and a green suite is not a
  waiver of a supported lost guarantee.

## Completed preparation and MOVE-1

| Completed outcome | Current owner and delivered result | History/evidence |
| --- | --- | --- |
| PA-1–PA-3 | Five older studies were reconciled and moved to `obsolete/`; the current [study](POST_M1_8_ABLATION.md#13-earlier-studies-absorption-and-archival-accounting) accounts for completed, rejected and deferred dispositions. This register is the only active AB plan. | Investigation at `549f3b4`, planning at `a7f8402`, five moves/reconciliation in `0c74ee7`; `build/post-m1-8-ablation-20260925/`, CHANGELOG. |
| MOVE-1 | Repeated source moves remain eligible through current unique correspondence while current hardlinks, duplicate identities and ambiguous pairs remain ineligible. [DATABASE](DATABASE.md), [PLANNER](PLANNER.md), [BUGS](BUGS.md) own the behavior. No schema, recorder or retained-history rewrite. | `build/move-history-20260925/` has native reproducer, 148 focused and 5,417 ordinary passes/five environment skips, imports and independent review; Git/CHANGELOG hold the commit. |

The prior M1-7 reduction register was retired, not passed. Its unfinished ideas
are accounted in the current study; no historical execution recipe resumes.
MOVE-1 preserves reviewed effects, current root/link evidence, unique mapping,
complete-scan refusal, bounded batched reads, one SQLite snapshot and ledger
history. The old historical-alias assertion was superseded only for current
correspondence; current pair-index, ordering, batching and snapshot guarantees
remain. A new performance claim was not made. Raw failed and passing receipts
stay at the evidence path above.

## M1-8 execution review closure

M1-8 delivered shared Plan/live/terminal status, bounded virtual rows, reachable
Details at native minimum, exact current-ledger distinctions, follow/Go, truthful
progress and capacity, retained action feedback, and task/session-owned Retry
updates including pending Close. Retry restores observation; it never restarts
execution. Admission, effects, terminal truth and close fences remain owned by
[BRIDGE](BRIDGE.md), [PRESENTATION](PRESENTATION.md),
[INTERFACES](INTERFACES.md) and [EXECUTOR](EXECUTOR.md).

| Closed outcome | Evidence and reviewed result |
| --- | --- |
| P2, R0–R2, post-R2, RC-1 | Reviewed commits `4bbf943`, `8f7555b`, `0fc2f5d`, `9e5b080`, `b1f5a07`, `c974447`, `96a0212`, `9be2930`, `3ea4e6b`. A1–A5 and B1–B6 pass: 5,405 ordinary passes/five skips, 33 installed GUI obligations and 12 imports. `build/m1-8-archive-20260924/evidence/recovery-close-20260924/` retains raw/failure/visual review and source/wheel/install checks. The three committed U-v2 artifacts retain the fixed 78-attempt results; [PERFORMANCE](PERFORMANCE.md#source-linked-historical-observations) owns the figures. |
| A6 integration | `build/m1-8-archive-20260924/integration.json` records non-squash merge `6c00ec731dd176d201e2a2c3a2a53b47652c544e` with tree `f7691c518a31a160f888db299faa9342bd9a4349` from candidate `cd2d44a802c665a4f76331b0a15856ef8102f1ac`; `postmerge_validation` is PASS. Evidence move/cleanup receipts and independent R3 review are preserved at the archive root. A6 is complete by this receipt, not inferred from test color. |

The accepted A1–A6/B1–B6 gate and the original finite delivery record remain in
[the archived register](obsolete/M1_8_DELIVERY.md). Prior failed R2 runs remain
failed. A green page capture does not establish native compositor health.
Seven recovery refs remain in a verified bundle; all task-owned dirty work and
unique evidence trees were accounted before cleanup. Unrelated GUI refs and
stashes were untouched. No old WIP is an integration unit.

## Remaining checkpoints

Completed GUI history is condensed below. [CHANGELOG](../CHANGELOG.md), Git and
the named evidence paths retain chronology. Active contracts belong to subject
owners; these rows do not reactivate old implementation recipes.

| Closed IDs | Delivered result, owner and pointer |
| --- | --- |
| GUI-1, GUI-S1–S21, GUI-R1–R2, GUI-I1–I3, GUI-D1–D7 | Task shell, Setup, Settings, bounded batch receipts, Fluent controls/icons and diagnostics. [DESKTOP_UI](DESKTOP_UI.md), [TOOLS](TOOLS.md), [BUGS](BUGS.md#desktop-material-composition), [M2_PROPOSAL](M2_PROPOSAL.md); CHANGELOG/Git through `2cc0083`. M2 retains native overlay scrollbar, verify-only batch and persistent preset proposals. |
| Plan GUI-P1–P3, scoped S1–S3, F1–F2, H1–H4, J1–J3, K1–K3, L1–L2, M1–M2, N/O/P | Rootless Plan table, complete server selection, counted filters, search, sibling sorting, exact bytes, row highlights, status controls and installed layout polish. [PRESENTATION](PRESENTATION.md), [BRIDGE](BRIDGE.md), [DESKTOP_UI](DESKTOP_UI.md); commits `27f1a6b` through `2cc0083` and matching CHANGELOG tasks. Historical scale receipts were not rewritten. |
| AI-1–AI-2, DOC-1/DOC-3 | Execution boundaries, frontend/M2 decisions and documentation ownership were reconciled. AGENTS and subject docs own current rules; CHANGELOG/Git hold history. |
| GUI-W1, GUI-WR1 | Advanced Color v3 observation suppresses specified dark flyout shadows on active WCG/HDR displays; independent review found no product correction. [DESKTOP_UI](DESKTOP_UI.md), [BUGS](BUGS.md#desktop-material-composition), [FEATURES](FEATURES.md); `c637025`, `build/wcg-review-20260924/`. Evidence does not prove a Windows compositor fix or isolate the review run's WCG-only selector; prior WCG-only monitor-move evidence remains separate. Mica remains required. |

The existing 48-pair bound, serial best effort, per-row options, exact uncertain
retry, keyboard/forced-color and admission guarantees remain active. Clearing a
batch receipt does not close a task. GUI-M2 recovery `af02913` and stash
`93414b7` are historical preservation, not merge units; useful changes were
rebuilt in `7cf4448`. The reported Optics refresh delay remains unprofiled.

DOC-2 remains **pending, outside this AB batch**: the historical branch
reconciliation proposal removes exactly four superseded compact-plan commits
from `milestone1`, preserves the old tip and opens a draft PR from
`milestone1-anthony`. Fresh divergence/remote-tip and work-preservation checks
are required before action; unexpected commits or unaccounted work require
adjudication. AB-1 neither executes nor closes DOC-2.

### Product delivery register

Each checkpoint is a closed register row. A new finding does not enlarge a row; apply the repository containment rules in `AGENTS.md`. A change begins only after its row has named the relevant active subject contracts and finite verification. The row's verification is in addition to ordinary affected department and consumer checks.

| ID | Accepted outcome | Dependencies and named verification | Status |
| --- | --- | --- | --- |
| M1-4 | Process-live blank task creation, navigation and explicit closure through existing lifecycle owners, with generation-aware callback containment. | Delivered in `ab453e1`; ordinary/headed checks and adversarial review passed. Active contracts are in BRIDGE and INTERFACES; concise delivery record below. | Complete |
| M1-async | Separate bounded command admission from asynchronous completion for create/start/release/close, reusing current task/session effect owners and one shared exchange budget. | After M1-4; default before M1-5, permitted after M1-5 but before M1-6. M1-async-G passed; delivered/excluded outcomes and evidence are below. | Complete |
| M1-5 | Give Setup and inventory one workflow-owned location-candidate pipeline with typed admission results and bounded remembered locations. | After M1-4, normally after M1-async. Verify parser refusals; leaf/reparse/placeholder and long paths; missing, offline, remount, and clone ambiguity; bounded recents; activation/slot races and purpose mismatch. Review path parsing and TOCTOU. Scanner, preflight, executor, and verifier retain fresh re-probes. | Complete |
| M1-6 | Deliver frozen, backend-canonical Setup, typed/picker/recent inputs, standalone inventory creation, serial best-effort pair creation, and explicit Plan-again after fresh reviewed-identity resolution. | Verify bounded inputs, canonical snapshots, immediate invalidation, no global-default mutation or browser filter normalization, partial-pair refusal, mixed batches, replay/recovery, slot/plan-generation races, and headed hostile-text/picker/recent flows. Map needed command behavior in BRIDGE when this activates; do not prescribe the retired 18-command expansion. | Complete |
| M1-7 | Deliver bounded plan review, selection, execution admission, and the full plan consumer for sibling sorting. A review remains truthful when execution never ran; an admitted attempt keeps its selection committed. | Exercise plan publication, selection and commitment freshness, stale/replayed mutation, admission-failure rollback versus post-admission preflight refusal, fresh Plan-again review after source/target changes, destructive confirmation, controls, windows/anchors/search/filter, and headed production flows. No terminal selection reopening or subset retry. BRIDGE and PRESENTATION define protocol and projection criteria. | Complete |
| M1-8-capacity | Distinguish recognized disk-capacity I/O failure and stop admission of later executor operations after settling the current operation. | Gate C passed with A8-02's explicit recorder-only/finalization boundary; existing failure-policy/Stop and settlement paths, unchanged oracle. | Complete |
| M1-8 | Deliver live and retained execution review with bounded item windows, exact execution overlays, task/item recording issues, terminal axes, current ledger evidence, capacity/generic-I/O messages, and informational trash location. | Test filesystem/recording combinations, overlay and omission invariants, Gap plus terminal reconciliation, navigation/re-observation, generic unrun presentation, yellow capacity without hiding known failures, bounded evidence queries, and post-copy overlay independence. Trash counts require complete outcome evidence; location-only fallback must not assert a planned count, scan all trash, or imply purge. | Complete; A1–A5 verified and A6 integration receipt PASS. |
| M1-9 | Deliver bounded inventory projections, current evidence, and the full inventory consumer for sibling sorting. | Test complete or prior-complete publication, warnings outside action scope, raw evidence provenance, search/filter/collapse/window/detail behavior, replacement/races, supported sort/reset production paths, and headed witnesses. | Pending |
| M1-10 | Deliver baseline, verify, and rebaseline controls plus the first same-task manual post-copy verification without persistent operation-time hashes. Rebaseline includes eligible null-evidence files and always hashes/replaces evidence; matching content is not a verified match. | Test acknowledgement admission before claim/native work; all-null and mixed rebaseline through workflow, service/CLI, and desktop; conditional-recording and supersession races; handoff classification; live pause/resume/cancel and unchanged automatic failed-read retries; and overlay/result identity boundaries. Terminal Verify-remaining/subset retry is deferred. Independently review the operation matrix and conditional-recording races. | Pending |
| M1-12 | First close integrated lifecycle/retention across activated task surfaces (absorbing former M1-11), then complete adversarial, documentation, ordinary, and headed verification. | Exercise plan-only, execution-only, linked/manual verification, inventory, refused, canceled, degraded, and failed tasks across navigation, reinjection, explicit close, and shutdown. Verify existing admission bounds, stale-response suppression, exact resource release and retained result truth; no aggregate-artifact or whole-owner-graph criterion. Run applicable settlement-oracle stability, ordinary/headed suites, installed-wheel/product witnesses, import checks, `git diff --check`, active-link checks, and independent cross-component review. | Pending |
| M1-Release | Produce beta packaging and release closure after delivery rows above are complete. | Build/test an installed artifact from a clean checkout; supply frozen specification/dependency/CI, notices and corresponding-source release material, standard-integrity host proof, and every applicable BR-G and SH-G gate. INTERFACES owns host/package and SH-G release criteria; BRIDGE owns BR-G evidence. | Pending |


## Delivered product checkpoints

| Closed row | Result and current owner | Commit/evidence pointer |
| --- | --- | --- |
| M1-4 | Process-live task creation, navigation, generation-aware callback containment and explicit close. [BRIDGE](BRIDGE.md), [INTERFACES](INTERFACES.md). | `ab453e1`; CHANGELOG and Git. No durable task survival was claimed. |
| M1-async | Bounded admission and completion for create/start/release/close, with one shared exchange budget and original effect/recovery owners. [BRIDGE](BRIDGE.md), [INTERFACES](INTERFACES.md). | `feat(web): add bounded asynchronous command completion` after `74aa6b7`; `build/m1-async/` and `build/m1-async-design/evidence/`. The native final-epoch/send guard remains. |
| M1-5 | Typed location admission and run-derived bounded recents with fresh point-of-use root evidence. [INTERFACES](INTERFACES.md), [WORKFLOWS](WORKFLOWS.md). | `e19ed9d`; `build/m1-5/evidence/`. Selecting a hint writes no recent record and grants no authority. |
| M1-6 | Frozen canonical Setup, picker/typed/recent paths, serial pair and standalone inventory starts, fresh Plan again. [BRIDGE](BRIDGE.md), [INTERFACES](INTERFACES.md). | `feat(web): deliver frozen task setup and location flows` after `b98dce4`; [archived study](obsolete/M1_6_SETUP.md), `build/m1-6/`. No global default mutation or partial-pair start. |
| M1-7 | Bounded Plan review, sibling sorting, committed selection and same-task execution. [PRESENTATION](PRESENTATION.md), [BRIDGE](BRIDGE.md), [INTERFACES](INTERFACES.md). | Through `5986c57`; P9 evidence `build/m1-7/evidence/p9-full-20260916/`, compact JSON and [PERFORMANCE](PERFORMANCE.md). R7-1–R7-4 later landed through `95f31e1`; unfinished R7-G is retired, not passed. |
| M1-8-capacity, E, P1, P2 | Capacity stopping after current settlement, bounded current-ledger evidence, exact retained execution review and overlays. [EXECUTOR](EXECUTOR.md), [DATABASE](DATABASE.md), [PRESENTATION](PRESENTATION.md). | `04947ba`, `7905a1b`, `055325b`, `4bbf943`; `build/m1-8-archive-20260924/`, CHANGELOG. Recorder-only failure remains independent degradation; P2 timing is superseded for the final UI by U-v2. |
| M1-8 R0–R3 | Installed execution review, recovery and coherent integration. Same owners plus DESKTOP_UI. | Final acceptance and exact A6 identity above; [archived register](obsolete/M1_8_DELIVERY.md). |

No completed row authorizes M1-9 inventory projection, M1-10 integrity controls,
M1-12 lifecycle closure or release. Their pending rows and criteria above remain
binding. Historical evidence proves only its recorded build/profile and does not
renew acceptance after a changed measured dependency.

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

Recognized operation, cleanup and destructive-prerequisite disk-capacity failure
stops later admission after current settlement under M1-8-capacity. Recorder-only
write failure remains recording degradation with continuation. Generic I/O keeps
its typed reason and has ordinary frontend presentation.
Yellow capacity mapping uses existing DESKTOP_UI semantics and never hides
independent known failures. Trash-location text is accepted for M1; exact
counting is conditional on complete outcome evidence. Location-only text is
displayed in execution Details. No filesystem inventory or purge is added to populate that information.

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
