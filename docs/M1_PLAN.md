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
dispositions. This section is the sole AB register. The original AB-1–AB-10 batch
authorization was later paused after AB-7. AB-7R/7S and recovery follow-ups are
delivered; AB-8 is delivered on 2026-09-26, with the requested recap pause now active.
Revision based on `0c74ee7` settled D2/D4; later delivered
checkpoints update the current transport contract in BRIDGE.

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
| AB-2 | Optional, usable performance drivers live in tools with required correctness/release checks preserved | AB-1 | 5,302 ordinary, 33 installed, 12 import passes; selected drivers, preserved evidence and independent review | Complete in `8ba38ced` |
| AB-3 | Unused database mapping API removed without changing current correspondence | AB-1 | 1,331 department tests, 12 import contracts, caller closure and independent review | Complete; reviewed `c5f1de8` integrated in `dd23c270` |
| AB-4 | Desktop selection capture avoids redundant work with one revision-bound handoff | AB-2 | 2,605 neighborhood; 5,305 ordinary; 4 installed; 12 imports; independent review | Complete in `9cfd2a0` |
| AB-5 | Bridge response adoption consolidates repeated traversal without weakening boundaries | AB-2 | 5,306 ordinary; 6 installed; 12 imports; response/custody/decoder checks and independent review | Complete in `1cb75fb` |
| AB-6 | Unsupported reload has one contained restart behavior instead of reinjection recovery | AB-2 | 5,317 ordinary; 34 installed; 12 imports; gestures, custody/close races and two independent reviews | Complete in `2b4a2214` |
| AB-7 | Existing admission/completion preserves original outcomes without page-timeout result abandonment or replay | AB-6; D2 settled | Delayed/post-effect failed delivery, bounded observation recovery/exhaustion, duplicate protection and close | Complete; original outcomes retained; installed34/34 and independent/Claude review |
| AB-7R | Reduce AB-7 recovery to command-specific authority and actual UI dependencies | AB-7; §14 validation and user authorization | Delayed/late results, qualified receipt recovery, current-state reconciliation, ordering/retirement, ordinary/imports and affected installed journeys | Delivered; separate AB-7R reduction commit |
| AB-7S | Consolidate recovery implementation and reduce tests to distinct product guarantees | AB-7R; user authorization 2026-09-26 | One attempt/settlement path, local outcome ownership, retained behavior matrix, ordinary/imports and installed journeys; independent review | Complete; separate reviewed product/test reduction |
| AB-8 | Existing shell renders bounded authoritative Python task snapshots | AB-4/5/6/7S | Producer→snapshot→page, ordinary/imports and installed task journeys | Delivered 2026-09-26; paused for user recap |
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
**Active boundary.** Base `29d9b8f` in isolated `codex/ab3-mapping`. Finite
population: `namisync/db/repositories.py`; direct consumers in
`tests/test_db_repositories.py` and `tests/test_workflows.py`; owning
`DATABASE.md`, this register, CHANGELOG and HANDOFF. PLANNER is a reviewed
unchanged consumer: its current-link, identity multiplicity and unique-pair
rules remain. Source, test and tools caller searches found no production/tool
call to the retired API; two repository tests use `get_mapping_snapshot`, and
one workflow fake rejects `find_mapping`. `MappingLookup`, `_mapping_pair`,
file-identity decoding and `find_current_mapping` remain live. MOVE-1's
current-scan correspondence and historical-alias disposition remain binding.
One atomic database refactor commit includes tests and matching docs, after
fresh independent review; no AB-2, schema/history, planner, workflow-runtime,
or speculative cleanup. AGENTS safety, recurrence and recovery stops apply.
Verification: characterize the two repository tests and native MOVE-1 cases;
then database/planner/workflows departments, imports, exact deleted-name
caller closure, documentation links/diff and adversarial review. Coordinate
broad suite execution with the AB orchestrator. Ignored `build/ab3-mapping/`
holds flat, descriptively named commands/logs/review evidence; remove only
task-created disposable files after integration accounting.
Local verification at the uncommitted candidate: seven focused MOVE-1/pair
round-trip cases passed before and after the edit; database/planner/workflows
departments passed 1,331 tests with 4,124 deselected; 12 import contracts,
deleted-name caller closure and diff check passed. The first focused attempt
failed in pytest setup on sandbox temp access and remains recorded; external
temp resolved it without altering tests. Fresh adversarial review passed after
correcting the review criterion to name the live query and planner owners.
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
**Adversarial review.** Verify the deleted path is unused, the current scan-scoped
query remains bounded, and planner safeguards still refuse ambiguous pairs and
current hardlinks/identity aliases.
**Commit gate.** Focused/neighborhood/import/doc checks pass;
`refactor(database): remove unused historical mapping lookup`.

#### AB-4 — Selection handoff without redundant construction

**Objective.** Merge L2/L3 as one change to desktop selection capture, avoiding
full public preview construction and unnecessary folder-wide work.
**Active boundary.** Integrated base `dd23c270` includes AB-2 `8ba38ced` and
reviewed AB-3 `c5f1de8`. Finite production population:
`namisync/interfaces/service.py`, `task_port.py`, and `web/drain.py`.
Direct test consumers: `tests/test_bridge_service.py`,
`tests/interfaces/web/test_drain.py`'s three lifecycle fakes,
`tests/test_task_lifecycle.py`'s port catalog, and the existing Plan review
and 120k scoped/highlighted selection cases. The migrated AB-2 performance
drivers in `tools/performance/plan.py` and `execution_receipt.py` call the
registry's public open path but do not consume the private handoff. Subject
owners are INTERFACES, BRIDGE, PRESENTATION, this register, CHANGELOG and
HANDOFF. `PlanProjection` already carries the workflow decision's immutable
selected membership, so the handoff adds only revision/state and aggregate
facts without a duplicate selected-ID collection. Preserve current artifact
identity, selection-state/revision/phase and drain task-generation barriers;
public CLI/API full preview, workflow safety/closure, destructive confirmation,
stale refusal, D4 highlight/checkbox separation and both membership reads for
mutations remain. No cache, new authority, projection topology change or
bypass flag. One atomic interfaces refactor commit includes direct tests/docs
after focused, interfaces/workflows/ordinary/imports and installed Plan gates,
with fresh adversarial review. AGENTS safety, recurrence and recovery stops
apply; no new stop class is needed.
**Characterization and candidate.** Eight named service/drain/Plan witnesses
passed at the integrated baseline. The local candidate then passed eleven
focused cases, including full-preview avoidance, immutable summary counts,
same-decision membership, lazy leaf resolution, folder safety, and rejection
of artifact replacement or a real selection mutation during projection build.
The public preview and mutation preview still construct operation-level views.
The interfaces/workflows neighborhood passed 2,605 tests; the ordinary suite
passed 5,305 with four supported-host privilege skips and 33 headed deselections.
Four selected installed Plan/execute cases and all 12 import contracts passed.
The fresh independent review found no blocking product or documentation issue;
the exact AB-4 commit is `9cfd2a0`. Evidence and the bounded design note live
in ignored `build/post-m1-8-ablation-20260925/`.
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
**Active boundary.** Integrated base `9cfd2a0` contains AB-3 integration
`dd23c270` and completed AB-4. The finite production edit is
`namisync/interfaces/web/bridge.py`; direct consumers to recheck are
`web/commands.py`'s typed continuation storage and drain codec binding,
`web/drain.py`'s typed prefix custody, `assets/bridge.js`'s detached native
response and whole-batch decoder, and the unchanged typed validators in
`interfaces/task_port.py` and `workflows/views.py`. The direct test population
is `tests/interfaces/web/test_transport.py`, `test_commands.py`, `test_drain.py`,
`test_browser_event_v5_consumers.py`, `test_frontend_static.py`,
`test_transport_headed.py`, transport-custody cases, `tests/test_task_lifecycle.py`
and `tests/interfaces/web/test_host.py` where they bind the drain codec. Subject
owners are BRIDGE, this register, CHANGELOG and HANDOFF; ARCHITECTURE changes
only if its locator changes. Capture and exact byte admission of hostile
values, owned typed validation, direct typed continuation storage, drain
validation before queue consumption, and browser detachment/identity adoption
remain separate boundaries. Consolidate only owned validation/projection over
the same detached value; registered validators retain their current traversal
coverage without duplicate nested calls. Preserve ingress, history write/readback,
workflow authority, exact longest prefix, scalar/cycle/type bounds and custody
release. No eager second primitive drain graph or generic trusted-value protocol.
Focused behavior before editing, interfaces/database/workflows neighborhood,
ordinary/imports, installed transport, documentation/diff checks and fresh
adversarial review gate one coherent bridge commit. AGENTS safety, recurrence
and recovery stops apply; no new stop class is needed. The ignored
`build/post-m1-8-ablation-20260925/ab5-design.md` records the read-only
population study and seams to refresh against this integrated base.
**Candidate and focused evidence.** Hostile capture and byte admission still
precede ownership validation. Ordinary response and test-fixture primitive
adoption now validate registered views during the detached projection walk;
the typed continuation and pre-consumption drain validators remain separate.
Registered validators retain their previous nested coverage. This reduces a
generic traversal, not source lines, and claims no timing or memory gain. One
shared-alias/caller-detachment witness was added. The 67-case focused baseline
passed before and after the edit; 228 response/serializer/codec/drain selected
cases and 14 refusal/decoder/continuation cases passed. Ordinary passed 5,306
with four unchanged privilege skips; six installed transport cases, 12 import
contracts and independent review passed. The first installed run selected an
old directory in its shared native-picker fixture; its five dependent failures
and ready receipt are retained beside the unchanged six-pass retry. No picker
repair or exact cause is claimed. Ignored
`build/post-m1-8-ablation-20260925/ab5-verification.md` holds commands and outcomes.
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

**Delivered (2026-09-25).** Genuine native content loading permanently retires
page command/appearance authority and every predecessor's response delivery.
Canceled navigation and fragment history do not retire authority; the native
adapter filters pywebview's canceled-completion reinjection. Browser reload
counters and shell reconstruction are removed. The replacement page gives fixed
close/reopen/fresh-plan guidance. Initial readiness, command identity, admitted
work and actual worker custody remain; X uses normal bounded retryable settlement,
including early replacement with no successor loaded event. No automatic
cancellation/release, renderer-crash recovery, S5 owner merger or AB-7 mutation
deadline/replay change. D4 and ordinary task observation/Retry updates remain.

**Verification and review.** Final corrected candidate: 5,317 ordinary passes,
four unchanged Windows symlink-privilege skips; all 34 installed headed cases
pass in one run; 12 import contracts kept. Installed reload holds an admitted
command through retirement, refuses new commands, observes one effect/actual
settlement and clean X. Same-document task/setup/execution journeys retain
selection, progress, mutation races and retry assertions. The transport fixture
now induces real same-document uncertainty instead of duplicate-ready recovery.
Independent review corrected repeated-document delivery retirement; the requested
Claude Opus 5.5/high review exposed the early-startup close latch, corrected and
accepted in the same session. Its independent held-worker and no-successor-load
witnesses pass. The original checkout was verified unchanged by both Claude
rounds; its disposable copy/CLI/fixtures were removed, with source evidence kept.

**Harness prerequisites and limits.** H1/H2 delivered in `f55a7dd` before product
work: Unicode edit readback, one native confirmation and actual returned-path
checks; original wrong-directory cause remains unconfirmed. Idle and active-work
gesture receipts show F5/Ctrl+R/Alt+Left did not navigate, mouse Back traversed
same-document fragments, and right click produced a DOM event without a sampled
owned native popup. This does not exclude other menu surfaces. The earlier
test-owned close-refusal popup came from a fixture-held worker; failure cleanup
now releases its own holds and preserves the initiating failure.

**Evidence.** Ignored `build/post-m1-8-ablation-20260925/ab6-verification.md`
maps raw successes, failed attempts, installed identity and both review reports;
`harness-verification.md` owns H1/H2 provenance. Subject contracts are in
INTERFACES/BRIDGE/FEATURES, presentation in DESKTOP_UI/PRESENTATION, and methods
in TESTS. Keep recovery `56802606` and AB-3 recovery worktree/ref for AB-10
accounting; never integrate recovery commits as-is. The extra Claude review
requirement applies to AB-6 and AB-7 only, not later checkpoints.

#### AB-7 — Original command completion and recovery (delivered 2026-09-26)

Applied D2 using existing native custody and asynchronous admission/completion.
Elapsed page time no longer abandons mutation results or replays mutations.
The twelve mutating wrappers, view/highlight operations and location admission
retain original identity; the interactive picker retains its separate wait.
Observation reads the original retained response without invoking its handler.
Three bounded observation attempts per round recover delayed/lost delivery;
exhaustion shows outcome unavailable and offers observation Retry where useful.
Captured fixed unknown effects retain intent fences without ineffective Retry.
Startup, read, lifecycle and resource-containment deadlines remain. Timed-out
async reads retain only bounded late-completion cleanup. D4 remains unchanged.

Close, starts/replacements, folder gestures and batch entry respect unresolved
intent. Pending Close preserves worker custody and has one receipt/terminal-
qualified continuation. Fixed-unknown review results keep their original fence;
a separate explicit Cancel may use the existing control owner for the same
active session, excluding unknown original Cancel and checkable/in-flight review
operations. Rail and handler share the Close reason. No new command-result
protocol, domain receipt owner, reload recovery or durable result store was added.

Verification: the complete run passed 5,353 cases with three installed failures
and four skips; all ordinary cases passed. The affected traced run passed 21.
Normal-asset installed acceptance covers all 34 cases across dependency-qualified
runs: 32 unaffected cases and both task-shell cases after native-state sampling
and eligible-click fixture corrections. Twelve import contracts passed. Independent source/evidence
review and Claude Opus5.5/high initial plus same-session follow-up passed after
validated corrections. The disposable review copy/private CLI were removed.

Limits: the earlier real Setup start exception did not recur; its cause remains
unclassified, not claimed fixed. Setup correctly preserved unknown effect and
stopped later batch starts. Source review identified that the task-shell fixture's
text-only wait did not ensure click eligibility; its corrected wait preserves
one real click. Diagnostic snapshots
did not capture the original Plan-again timeout's exact cause.
Keep the failed receipts and bounded test diagnostics for recurrence. A picker
whose native return never settles has no automatic observation timer; process
loss still has no guaranteed result recovery. These are not new replay authority.

Evidence: ignored `build/post-m1-8-ablation-20260925/ab7-verification.md`, raw
complete/diagnostic/installed receipts, `ab7-independent-review.md` and
`ab7-claude-review.md`; the evidence index retains both reviewed correction decisions.
Atomic commit: `refactor(web): simplify command completion without timed mutation replay`.
Pause for user recap; AB-8 implementation remains unauthorized.

#### AB-7R — Reduce command recovery and uncertainty state

Delivered 2026-09-26 on `milestone1`, base `895710fb`, as one separate
reviewed reduction checkpoint. Outcomes and verification are recorded below;
frozen inputs and failed receipts remain in ignored AB-7R evidence. AB-8 remains paused.

- **R1/R2:** Five commands no longer retain/observe original responses: picker,
  location admission, view, highlight and cosmetic replacement. Revisioned
  Refresh or deliberate folder rechoice supplies current authority, without
  claiming the earlier effect settled. Row/review/theme ownership rejects stale
  replies; only the latest resolved folder choice feeds Start/batch. Pending
  folder admission can be removed or detached by origin Close before Create.
- **R3:** Eleven effect/lifecycle commands retain original observation. Receipt
  retirement, selection replay's current projection and execution's unretained
  no-effect dispositions prevent blanket receipt-based resend. Production drain
  start receipts also coordinate Close. No new protocol, store or domain owner.
- **R4/R5:** Bounded observation updates delayed/unavailable feedback and offers
  read-only Check. The original promise is the sole result adopter; valid late
  completion updates its owner automatically. Remove duplicate retry/adoption
  branches and unrelated presentation/folder fences. Keep actual selection→Execute,
  start/Close and retirement dependencies, duplicate protection, D4 and resource
  bounds. No elapsed-time mutation abandonment or automatic replay.

Ten production files and fourteen test/probe consumers changed. Production is
net 55 lines smaller (+556/-611); tests net 157 larger (+487/-330). This is a
mechanism reduction, not a large source reduction. Native service/lifecycle,
drain, slots and domain owners remain unchanged. Independent review corrected
picker pending cleanup after unrelated form edits and misleading folder feedback.
The first installed gate exposed an obsolete Setup callback requirement; its
constructor reproducer failed before removal and passed afterward.

Verification: ordinary run 5,323 passed/4 skipped plus one obsolete policy
expectation, corrected before the full current interfaces rerun (1,785 passed).
Unchanged domain/tool results are reused by dependency; all 34 installed headed
cases passed on the corrected frozen build. Twelve import contracts passed;
fresh adversarial source/evidence review and documentation checks passed.
Evidence: `build/post-m1-8-ablation-20260925/ab7r-verification.md`,
`ab7r-frozen-inputs.json`, `ab7r-review.md` and named XML/log receipts.
Earlier unexplained AB-7 Setup/Plan-again observations are not claimed fixed.

#### AB-7S — Consolidate recovery and its behavioral tests

**Complete, 2026-09-26**, on `milestone1` from `d4351acd`, as one separate
checkpoint before AB-8. Browser commands share one request registry and
direct/async result settlement path, with optional original-result observation.
Review uncertainty lives on the retained review; control Check lives on its
issuing attempt. Fixed review/control errors allow explicit exact-session Close
through existing native cleanup. Unknown start/execution/release/Close fences,
selection→Execute, D4, late result adoption and custody bounds remain.

Production is net **357 lines smaller**, tests **330 smaller**. Retired helper
spelling/branch pins, repeated policy/envelope assertions, fake effect counting
and the tracer's copied eligibility policy. Keep browser admission rejection,
real native post-effect recovery and distinct queued-row/control/Close journeys.
Independent review caught a Check-disabled projection still reading its former
owner; its renderer witness failed before correction and passed afterward.

Verification: ordinary 5,321 passed/4 skipped; final interfaces refresh 1,782
passed after the renderer/test correction, retaining unchanged domain/tool
evidence by dependency. All 34 installed headed cases and 12 import contracts
passed, plus fresh independent review and documentation checks. Evidence:
`build/post-m1-8-ablation-20260925/ab7s-verification.md`, final input hashes,
review, deletion maps and XML/log receipts. The expanded pre-close register is
retained with that evidence.

Native domain/receipt owners and wire protocol are unchanged. No blanket resend,
new store, selection demotion through cached reads, or AB-8 implementation.
Earlier unexplained AB-7 observations remain unexplained. AB-8 stays paused;
retain pre-existing AB-3/AB-6 worktree/recovery records for AB-10 accounting.

#### AB-8 — Authoritative task snapshots and bounded shell refactor

**Delivered, 2026-09-26.** The Python desktop adapter now owns one bounded
presentation reducer per task/session. Drain publishes a detached versioned
snapshot with its byte-admitted prefix; staged failure cannot consume queue
custody or advance presentation state. Native replay preserves newer facts and
explicit Gap uncertainty. Terminal truth does not certify item completeness.
Item windows and one-detail reads retain their independent bounds and owners;
the snapshot carries no outcome map.

The existing shell adopts supplied facts and formats progress/rate/ETA. Browser
transport cursor, replay, callback retry and actual terminal-delivery custody
remain; local interaction, D4, command recovery and pending Close are preserved.
CLI/history events and domain effect authority are unchanged. Real producer,
native reduction and page-adoption tests replace browser semantic reduction
tests; direct diagnostic consumers handle snapshot-only callbacks.

Review corrections scope snapshot lifetime/revisions to the current session,
prevent a retained Plan result or Gap from becoming execution truth, preserve
aggregate rate samples across ordinary item/outcome handoffs, and retire settled
control feedback when authoritative control state arrives. Focused red/green
witnesses cover the lost guarantees. The earlier larger-window stack/wrap
assertion passed unchanged on rerun; its cause remains unexplained.

Acceptance: complete suite **5,366 passed, 4 Windows symlink-privilege skips**,
including installed journeys; **12 import contracts kept**; fresh independent
source review and Opus 5.5/high re-review; documentation links/diff checked.
Evidence and recovery chronology: `build/ab8-20260926/` and
`build/ab8-resume-20260926/verification.md`; the expanded activated boundary is
retained in the latter directory. Recovery `f7a170a` was reconstructed as a
coherent change on base `4f1537c2`, never merged/cherry-picked.

This consolidates ownership rather than producing a large source reduction:
product +68 lines, tests -181, tooling +1 before documentation. The Plan-again
tracer remains useful for command admission/effect diagnosis. S5's settlement,
observer/dispatcher cleanup and plan-retirement joins remain deferred. No
framework, new command protocol, S5 merger or AB-9/10 implementation shipped.
**Pause for user recap before further checkpoint implementation.**

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

- Current checkpoint: AB-1/AB-2/AB-3 complete; the full AB batch is active;
  remaining rows await their named dependencies, not repeated activation.
- Existing evidence: `build/post-m1-8-ablation-20260925/` contains the study,
  AB-1 checks and AB-2 migration map, selected reports, raw failed child logs,
  focused results, `ab2-ordinary.log/xml`, `ab2-raw-json-verification.json`
  and history/bridge lane receipts. Five archived studies are accounted in the
  current study §13.
- AB-1 verification: `ab1-checks.json` and `ab1-review.md` in that evidence root
  record documentation-only scope, 320 links, source figures, matching A6 trees
  and independent review/correction. No product tests are an AB-1 gate.
- Next action: refresh AB-4's prepared design against the integrated tree,
  then activate its bounded selection handoff. The frozen AB-2 tool/consumer source
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
| M1-12 | First close integrated lifecycle/retention across activated task surfaces (absorbing former M1-11), then complete adversarial, documentation, ordinary, and headed verification. | Exercise plan-only, execution-only, linked/manual verification, inventory, refused, canceled, degraded, and failed tasks across same-document navigation, contained unsupported reload, explicit close, and shutdown. Verify existing admission bounds, stale-response suppression, exact resource release and retained result truth; no aggregate-artifact or whole-owner-graph criterion. Run applicable settlement-oracle stability, ordinary/headed suites, installed-wheel/product witnesses, import checks, `git diff --check`, active-link checks, and independent cross-component review. | Pending |
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
