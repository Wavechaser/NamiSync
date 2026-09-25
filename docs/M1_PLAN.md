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

Planning baseline: `milestone1` at `a7f8402`, plus this session's documentation
reconciliation and five study moves. Source investigation is against that product
revision; recheck changed seams before implementation. The
[study](POST_M1_8_ABLATION.md) owns findings, source evidence and compact rejected
dispositions. This section is the sole AB register. The requested commit records
the plan and prior reconciliation; **all AB checkpoints remain pending**. Plan
creation/approval does not by itself activate implementation.

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
  D2 remains a user decision: AB-7 recommends prompt admission and authoritative
  result observation without timer-driven mutation replay. The user may instead
  retain current commands; AB-8 can then proceed using them. No silent timeout
  deletion or indefinite pending state. D4 remains unchanged: keep highlighting
  separate from execution checkboxes. D6's missing-row acknowledge/restore UI
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
| Host document generations and `bridge.js`/`app.js` command attempts; lifecycle/observer cleanup | Late retired-page callback gains authority, timeout duplicates an effect, close drops live ownership, unavailable backend looks perpetually active | AB-6/7: installed gestures, delayed/duplicate returns, close races and failed observation; preserve task-lifecycle concurrency tests |
| Event bus Gap → SessionObserver → drain `_TaskState` → JS reducers → shell controls/windows/details | Removing browser reduction fabricates completeness, loses terminal axes, misroutes task state, rounds large integers or drops control/Close feedback | AB-8: real producer→snapshot→page scenarios, bounded windows/one detail, navigation and deferred-response probes plus installed journeys |
| Static CSS/source pins, design tokens and gallery | Removing a spelling assertion also removes focus, reduced-motion, forced-color or safe-sink detection | AB-9: retained semantic/computed-style/native witnesses; no whole-cohort deletion |

### Checkpoint register

Dependencies are minimum prerequisites. Execute in the listed order by default;
independent rows can be reordered when activated. Each row has one coherent
commit. Shared test retirement travels with its owning behavior, not in a later
cleanup commit. New findings do not silently add rows.

| ID | Accepted outcome | Depends on | Primary verification | Status |
| --- | --- | --- | --- | --- |
| AB-1 | Documentation/workflow ownership is clear; delivered records compact; PERFORMANCE established | Activation | Owner/decision accounting, extracted figures, links/diff and adversarial review | Pending |
| AB-2 | Optional, usable performance drivers live in tools with required correctness/release checks preserved | AB-1 | Tools/interface consumers, ordinary/imports, installed helper consumers and representative driver smokes | Pending |
| AB-3 | Unused database mapping API removed without changing current correspondence | AB-1 | Database/planner/workflow neighborhood and caller closure | Pending |
| AB-4 | Desktop selection capture avoids redundant work with one revision-bound handoff | AB-2 | Selection/service/task-port consumers, counted work and installed Plan | Pending |
| AB-5 | Bridge response adoption consolidates repeated traversal without weakening boundaries | AB-2 | Response/custody/decoder consumers, ordinary and installed transport | Pending |
| AB-6 | Unsupported reload has one contained restart behavior instead of reinjection recovery | AB-2 | Host/transport/lifecycle races and installed gestures | Pending |
| AB-7 | Command admission/result observation no longer requires timer-driven mutation replay | AB-6 and explicit D2 decision | Duplicate/delayed/failed command and close composition | Pending, decision required |
| AB-8 | Existing shell renders bounded authoritative Python task snapshots | AB-4/5/6; AB-7 completed or explicit current-command retention | Producer→snapshot→page, ordinary/imports and installed task journeys | Pending |
| AB-9 | Remaining visual/source pins protect behavior rather than incidental spelling | AB-8 | Static/security, computed style, ordinary and installed gallery | Pending |
| AB-10 | Integrated reductions preserve the complete retained workflow and have coherent docs/evidence | All above; AB-7 disposition recorded | Overall final sweep below | Pending |

### Detailed checkpoints

#### AB-1 — Documentation first

**Objective.** Establish the documentation and workflow rules before moving
machinery or changing acceptance. Merge W1/W2/W4 and the remaining W3 accounting
because they deliver one consistent set of owners and recording rules.

**Scope and approach.** Edit AGENTS, ARCHITECTURE, DEFENSE ownership routing,
TOOLS, TESTS routing, README, M1_PLAN, PRESENTATION, relevant BRIDGE/INTERFACES
links, the study, CHANGELOG and HANDOFF; create `docs/PERFORMANCE.md`. Audit
FEATURES only for duplicated implementation prescriptions touched by this pass.
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

**Scope and approach.** Move Plan, M1-8 receipt/UI, bridge-event and history
measurement entry points and measurement-only helpers/assets into
`tools/performance/`. Reuse the existing `python -m tools` entry point with a
planned `performance` subcommand for listing/selecting cases and output paths;
these commands do not exist yet. Keep safety/custody and release assertions in
their existing test owners. Before edits inventory references in all `tests/`,
`tools/`, docs and packaging: especially `_setup_headed_child.py`,
`_task_shell_headed_child.py`, `test_headed_evidence.py`, the three scale test
modules, benchmark tests and `_departments.py`. Separate shared functional
fixtures from obsolete readiness/authority machinery instead of copying them.
Tools must not import collected tests; tests may use tools-owned fixtures.

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

#### AB-7 — Command result observation (D2 conditional)

**Objective.** Remove timer-induced mutation uncertainty without losing duplicate
protection or feedback. Requires explicit user choice of the proposed behavior;
retaining current commands is a valid disposition, not a failed implementation.
**Scope and approach.** Existing command admission/completion owner, task-port,
bridge exchange, app attempt handling and lifecycle consumers. Before editing,
record command-by-command admission/result/close transitions in BRIDGE. Reuse
authoritative identities and bounded result observation. Long close settlement
becomes observable task state; a slow response is neither cancellation nor a
reason to resubmit mutation. Keep bootstrap/shutdown/job bounds. Backend loss
must become visible with a safe observation/restart route, not perpetual pending.
**Acceptance criteria.** Duplicate gestures/late returns produce at most one
effect; response loss recovers the original result; pending Close reaches an
honest settled or unavailable state. No automatic timeout-triggered mutation
replay. CLI behavior, admission rollback and current recovery limitations remain.
**Regression watchlist.** Result eviction before observation, close/start races,
ambiguous native failure, double confirmation and stale task navigation.
**Tests and evidence.** Command, lifecycle and transport tests with deliberately
delayed/lost/duplicate results and unavailable backend; interfaces/workflows
neighborhood, ordinary/imports and installed submit/control/close/reobserve flows.
**Documentation and handoff.** BRIDGE/INTERFACES own the chosen transitions; retain
exact unavailable-backend UX and lifetime bounds. If user retains current policy,
record that disposition and AB-8's dependency without pretending AB-7 shipped.
**Adversarial review.** Follow each admitted effect whose response never reaches
the page; establish how the user learns its outcome without starting it again.
**Commit gate.** Approved command contract, all failure paths and consumers pass;
`refactor(web): observe admitted command results without timed mutation replay`.

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
AB-7 must be completed or explicitly disposed as current commands retained before
freezing the snapshot shape. No framework, preparatory shell rewrite or S5 merger.

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
deferred decisions, list remaining M1-9/10 allocation and D4/DOC-2 decisions.
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
unsupported reload and shutdown, including refused/degraded/capacity cases.
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

- Current checkpoint: AB-1 pending activation. This revision is planning and
  prior-reconciliation delivery only; no AB checkpoint is complete.
- Existing evidence: `build/post-m1-8-ablation-20260925/` contains study runs,
  scripts and `reconciliation-checks.json`; five archived studies are accounted
  in the current study §13. No product tests or new benchmarks run for this plan.
- Next action: activate AB-1, then its documentation-only population/verification;
  preserve current gate status until AB-2 moves producers and consumers together.
- Commands: final sweep above; current documentation check is
  `.\.venv\Scripts\python.exe build\post-m1-8-ablation-20260925\scripts\check_reconciliation.py`
  against the planning baseline before commit. This one-shot checker is not a
  permanent project gate or valid unchanged after AB implementation.
- Decisions: D2 needs user selection before AB-7; explicit retention allows AB-8.
  D4 feature behavior unchanged, D6 scheduled allocation later, S5/L6/tracer
  retirement deferred. Rejected L5/L7/L8/L9 stay in the study's compact table.
- Preserve all raw JSON, existing build evidence, unrelated work, branch refs and
  stashes. No DOC-2 operations, push or PR. Commit only verified task-owned docs.
- Stop for AGENTS mandatory safety conditions, changed accepted outcome/ownership/
  safety boundary, or recurrence thresholds. Investigate finite affected consumers
  before proposing escalation; do not silently grow this register. A red test of
  a retired mechanism alone is not a safety stop, and a green suite is not a
  waiver of a supported lost guarantee.

## Post-M1-8 ablation reconciliation (2026-09-25)

Documentation-only scope at `a7f8402`: reconcile D1–D7 and S3's accepted
direction; investigate S4/S5 and shell timing; narrow E1/W1–W4; account for
and retire the five earlier reduction studies. The decision and source map is
owned by [POST_M1_8_ABLATION](POST_M1_8_ABLATION.md). Product/tests, operative
evidence policy, AGENTS and pending product checkpoints are unchanged.

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| PA-1 | Reconcile proposals against current owners and user dispositions | Source/consumer inspection and explicit retained boundaries | Complete |
| PA-2 | Absorb useful pending study findings and preserve binding decisions before archival | Five-study disposition, preserved-body comparison and incoming-link audit | Complete |
| PA-3 | Deliver one consistent current study and resumption record | 192 local links, diff checks and final adversarial consistency review | Complete |

Non-goals: implementation, benchmark/test retirement, safety-policy changes,
or resumption of old implementation registers. Stop for a newly established
mandatory safety condition or a required change outside this documentation
population; investigation findings alone do not authorize fixes.

## MOVE-1 retained-history move detection (2026-09-25)

User-authorized backend investigation and correction, independent of pending
GUI work. Base: `3514bb8`; current checkout `milestone1`. One atomic fix commit
after independent review; no push, PR or live development-ledger mutation.

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| MOVE-1 | Repeated source renames/moves remain eligible for correspondence-backed target moves despite retained historical inventory aliases; real simultaneous hardlinks and ambiguous correspondence remain ineligible. | Native failure reproduced before correction; 148 focused checks; 5,417 ordinary passes/five environment skips; 12 imports; diff/link checks; fresh adversarial review. | Complete in the commit recording this row |

Finite population: planning correspondence in `db/repositories.py`, its direct
consumer `workflows/runtime.py`, planner move eligibility in `modules/planner.py`,
and existing `test_db_repositories.py`, `test_planner.py`, `test_workflows.py`.
Recorder retention/reconciliation, scanner links, workflow completeness and
service Plan projection were inspected without changes. Documentation owners:
DATABASE, PLANNER, BUGS, this register, CHANGELOG and HANDOFF; README only if its
phase synopsis changes (none needed). Preserved the prior investigation in
`build/move-history-20260925/handoff-before.md` before replacing it at delivery.
That ignored evidence directory holds flat, descriptively named logs and review
notes, plus named pytest temporary-root subdirectories when the system temp
directory is unavailable; retain evidence at closeout, with no artifacts in Git.

Preserved guarantees: reviewed effects, current source/target identity and link
checks, unique correspondence, incomplete-scan refusal, query admission/batching,
one SQLite read snapshot, ordering, retained inventory/history and ledger schema.
Verified repeated native move/no-op cycles with retained aliases; current
source/target links, including outside-root/excluded links; stale multi-link
observations; duplicate scan identities/pair ambiguity; and consistent batched
reads. Archived M0 hardlink refusal remains binding. No performance claim added.
Non-goals: ledger cleanup/migration, identity-reuse redesign, GUI behavior,
inventory reconciliation changes, broader planner refactoring or unrelated bugs.
AGENTS mandatory safety/recurrence stops apply; changed effect or ownership
boundaries require adjudication before implementation.

Shipped: remove historical disqualification only from `find_current_mapping`;
current `FileRecord.nlink` and planner identity counts own current alias
eligibility. General inspection remains conservative. No path/presence filter
can make a retained observation fresh. Production edits are confined to
`db/repositories.py`; the three test files above cover the affected seams.
Obsolete identity-query assertions became pair-query batching/index and
concurrent correspondence snapshot controls without retiring their guarantees.
Archived DESIGN_REVIEW DR-04's correspondence and hardlink evidence obligation
remains satisfied by retained pairs plus current scans. No recorder, schema,
workflow, scanner, preflight, executor or interface production change is needed.
The completed TEST_REFINEMENT ST-2 register described historical alias-query
assertions at its frozen source revision. MOVE-1 supersedes only that obsolete
alias-query mechanism; its current pair index, batching, ordering, identity
filtering and snapshot guarantees remain binding. FEATURES already describes
hardlink refusal in terms of scanned paths and needs no contract change.

Evidence: `build/move-history-20260925/` contains the native pre-fix failure,
`focused-final2.log`, `ordinary-final.log`, imports, links, and independent
`reviewer-readonly.md`. The first ordinary attempt used repository-local temp
roots and hit protective test refusals; its failed receipt is retained. The
final run uses normal external temp roots and the final frozen source/tests.
Five skips: unavailable symlink privileges (four) and unconfigured M1-7 readiness
artifact (one); 33 headed tests are outside this backend-only change. No extra
branch/worktree, live user-data mutation or unrelated change was introduced.

## M1-8 execution review closure

Delivered: shared Plan/live/terminal status, bounded virtual rows and reachable
Details at native minimum, exact execution/current-evidence distinctions,
follow/Go navigation, truthful progress and capacity feedback, retained action
feedback, and task/session-owned Retry updates including pending Close.
Operational admission, terminal truth, close fences and effect authority are
unchanged. Retry restores observation; it never restarts execution.

| Outcome | Reviewed commit / disposition |
| --- | --- |
| P2 foundation | `4bbf943`; bounded live/retained overlays and one-detail custody. |
| R0 usable execution review | `8f7555b`; A1–A4 and B1–B6 closed. |
| R1 functional consolidation | `0fc2f5d`, corrections `9e5b080`; retained semantic/native detectors. |
| R2 quantitative consolidation | `b1f5a07`, `c974447`; U-v2 observers and fixed 78-attempt acceptance. |
| Post-R2 containment/control fixes | `96a0212`, `9be2930`; automatic probe bounds and task-owned control feedback. |
| RC-1 observation recovery | `3ea4e6b`; separate reviewed correction, fresh affected gates and U evidence. |
| R3 integration | A6 below defines the terminal observation; no WIP or unrelated GUI recovery enters the merge. |

### Final acceptance ledger

Evidence root **E** is `build/recovery-close-20260924/` inside the candidate.
After cleanup the entire directory is preserved at
`build/m1-8-archive-20260924/evidence/recovery-close-20260924/` in the main
checkout. E's `delivery-01.json` binds RC-1 `3ea4e6b1b59d700428440c45cc845f68d852eeae`, its Git tree,
artifact hashes, raw logs and independent review. All package inputs, wheel
members and installed files are compared physically; the U authority records
the fixed runtime/native profile and measured source population.

| ID / accepted outcome | Owning detector and evidence | Result / review disposition |
| --- | --- | --- |
| A1 usable layout; B1/B2 | Existing gallery's eight disclosure/size/row states, native keyboard/scroll and bounded-window adoption; E `builder/consumer-headed-pytest.txt`, `captures/`, `review/visual-review.md`. | Pass on final installed product; native minimum 1024×640 retained. Raw browser alpha captures are not native-material contrast evidence. |
| A2 identity/interaction; B6 | Task-shell/drain/row probes, deferred-response controls, follow/Go sequences and native task-shell recovery/Close witness; E `ordinary-01.log`, `builder/rc1-builder-report.md`, `headed-01.log`. | Pass; exact task/session/revision, bounded 256-row window/one detail, stale rejection, control feedback and retirement remain distinct. |
| A3 truthful facts; B6 | Producer, reducer and execution-review tests plus rendered row/status witnesses in the ordinary and installed suites. | Pass for success/zero/unrun/canceled/degraded, capacity plus independent failure, Gap/terminal and exact large-byte progress. No changed ingress, mutation or safety authority. |
| A4 installed composition; B3/B4/B5 | E `headed-01.log`: 24 unaffected passes; nine gallery/transport passes after two direct test-consumer migrations, E `builder/consumer-headed-pytest.txt`. Both short copies/details/PNGs and both legacy native journeys pass. Full source/wheel/install identity in `run-01/head-validation.log`. | All 33 obligations pass; failed original headed attempt preserved. E `review/RC-review.md` and visual review name actual evidence and limitations. |
| A5 fixed performance | Three `tests/interfaces/web/m1_8_execution_ui_*.json` artifacts; E `run-01/` raw/freeze/derive/staged/HEAD validations and `artifact-controls-01.log`. | All 78 attempts: 13 readiness + 65 measurement children, 40 cold/150 warm samples. Unchanged cold max ≤50ms, warm nearest-rank p95 ≤100ms/max ≤250ms; independent raw derivation passes. Historical failed R2 runs remain failed. |
| A6 coherent integration | E `review/R3-review.md`, `accounting/`; main `build/m1-8-archive-20260924/integration.json` records non-squash merge, exact candidate/merge tree and passing postmerge source/package/artifact identity. `evidence-move.json` and `cleanup.json` record preservation and cleanup. | Functional gates: 5,405 ordinary passes/five skips, 33 installed GUI obligations and 12 imports. Complete only when the integration receipt records the matching merge/tree and PASS; receipt absent means integration remains open. |

The integration receipt is the terminal observation; this register does not
claim completion before it exists. Independent reviews cover the complete
P2-to-final delta, not only RC-1. Seven recovery refs are preserved in a verified
bundle; four dirty detached-worktree files and every unique build-evidence tree
are accounted before removal. Unrelated GUI refs and all stashes stay untouched.

Stop after M1-8. Filter/Search, speculative theme changes, M1-7 reduction-study
resumption, general test-framework changes, M1-9, push and PR are excluded.
The former M1-7 reduction register is now retired; useful unfinished proposals
and retained guarantees are accounted in [POST_M1_8_ABLATION](POST_M1_8_ABLATION.md#13-earlier-studies-absorption-and-archival-accounting).
Future product and release obligations below remain binding.

## Remaining checkpoints

### Completed GUI and documentation work

Completed records are condensed here; CHANGELOG and Git history through
`2cc0083` retain individual deliveries, studies, verification and exact diffs.
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
| Plan-surface GUI-P1–P3 (2026-09-17) | Plan/Status cards, resizable rootless virtual table, sibling-sort gestures and exact byte display. `27f1a6b`, `4053a53`, `6425fa7`, `db46269`; component and installed Plan/gallery checks. [DESKTOP_UI](DESKTOP_UI.md), [PRESENTATION](PRESENTATION.md). |
| Scoped Plan GUI-S1–S3 (2026-09-17) | Revision-guarded header/folder selection over complete filtered membership, hidden selections preserved, synthetic root omitted. `f3bd84f`, helper correction `87dbd49`; ordinary/installed checks and 120,000-operation scoped-cost witness. These IDs are distinct from the earlier Setup GUI-S rows. [PRESENTATION](PRESENTATION.md), [BRIDGE](BRIDGE.md). |
| GUI-F1–F2, GUI-H1–H4 | Editable queued search, counted filters, stable panel/row refresh, server-owned highlights and atomic highlighted selection. `ae99f54`, `218866b`; ordinary, browser, installed and 120,000-row checks. The empty-rootless Setup witness noted in GUI-F was corrected during GUI-J. [PRESENTATION](PRESENTATION.md). |
| GUI-J1–J3, GUI-K1–K3 | Grouped filters, compact viewport/task digest, neutral Plan-ready meaning, layout and status polish; directory own-operation eligibility corrected independently of descendant rollups. `44a5d49`, `4ef526e`, `f8bc1aa`, `0584707`; focused, department and installed default/larger Plan checks. Shared byte formatting was superseded by GUI-O below. [DESKTOP_UI](DESKTOP_UI.md), [PRESENTATION](PRESENTATION.md). |
| GUI-L1–L2 | Fluent control/gallery alignment and server-owned arrow navigation across windows, preserving pointer focus modality. `dd926b8`, `e6ee448`; component, interface and installed gallery/Plan checks. [DESKTOP_UI](DESKTOP_UI.md). |
| GUI-M1–M2 | Status actions/feedback and static destination-tree folder totals from retained file facts; partial/overflow facts remain explicit, numeric sorting stays server-owned. `70a9270`, `7cf4448`; workflow/interface, independent scale-fixture sums, scalar boundaries and installed Plan checks. Historical scale receipts were not rewritten. [PRESENTATION](PRESENTATION.md), [DEFENSE](DEFENSE.md). |
| GUI-N, GUI-O, GUI-P (2026-09-19–20) | Friendly labels and selective low-risk notes, fixed semantic icon slots, immediate planning feedback, exact bytes below 1 KiB/two decimals above, tertiary text and final spacing/alignment. `c552537`, `8fd8cd0`, `2cc0083`; focused/department and installed gallery/default/larger Plan checks. [DESKTOP_UI](DESKTOP_UI.md). |


GUI delivery evidence remains in the matching CHANGELOG tasks and those commits'
HANDOFF snapshots. Intermittent installed dialog/confirmation failures were
retained as failed attempts; unchanged isolated reruns passed without weakened
assertions. GUI-P's last evidence root is
`C:/Users/Spectrum/.codex/visualizations/2026/09/18/01a0b2ed-22b3-7083-a3e1-21f00596391d/`.
GUI-M2 recovery `af02913` and stash `93414b7` remain historical preservation,
not merge units; useful changes were rebuilt in `7cf4448`. The reported Optics
refresh delay remains unprofiled; no cloud/path diagnosis was established.

No rendering fix was established for the WCG shadow halo or intermittent
disabled-label blur. Mica remains required and no compositor-health release gate
was added. GUI-D8–D10 attributed the halo to Windows Advanced Color composition;
GUI-W1 below adds a mitigation, not a fix. BUGS and DESKTOP_UI retain
investigation boundaries and reopen evidence. Recent availability remains observation, never admission.
The existing 48-pair bound, serial best effort, per-row options and exact
uncertain retry remain active; clearing receipts does not close tasks.

### GUI-W1 Advanced Color shadow mitigation (2026-09-24)

User-activated after M1-8; it does not resume other excluded work. Evidence
and diagnostics: [BUGS](BUGS.md#desktop-material-composition).

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| GUI-W1 | While the window's current display has Windows Advanced Color active (SDR WCG or HDR), dark flyouts (dialogs other than keyboard-focused, menus, combobox popups) suppress CSS elevation shadows exactly as the existing dark HDR rule does. Native appearance reads the state for the window's monitor, refreshes it on display-setting changes, monitor changes and activation without reapplying material, and publishes it in the exact appearance envelope (v2 → v3). Read or observation failure keeps the prior value and degrades like other appearance observation. | Controller/fake-native publication, refresh, failure and close tests; page receiver probe for the v3 schema; token rule assertions; installed gallery report on this WCG display recording `advanced_color` and suppressed popup shadow; ordinary interface departments; import contracts; `git diff --check`. | Complete in the commit recording this row |

Population: `appearance.py`, `appearance.js`, `components.css`; their tests,
the appearance probe and the gallery evidence path; BUGS, DESKTOP_UI,
FEATURES, CHANGELOG and HANDOFF. Non-goals: fixing the Windows defect, scRGB
or other renderer flags, light-theme or card-level changes, pre-distorted
tokens, removing the HDR media rule. Stops: any change to Mica/opaque material
selection, surface-safety settlement or command/readiness authority.

### GUI-WR1 mitigation review (2026-09-24)

User-authorized review of `c637025` against `6c00ec7`, limited to its native
Advanced Color observation, appearance-v3 producer/receiver, shadow selectors,
direct test/helper consumers and GUI-W1 documentation. Preserve material and
surface-safety decisions, readiness authority, light-theme shadows and keyboard
focus. No new GUI features, compositor fixes or unrelated harness cleanup.

| ID | Accepted outcome | Named verification | Status |
| --- | --- | --- | --- |
| GUI-WR1 | Review the GUI-W1 mechanism and consumer migration; correct concrete in-bound defects if found, with a reproducer and finite correction population recorded before implementation. | Independent native/API review; source/consumer inspection; 165 focused checks; three installed gallery passes and the fourth passing unchanged in isolation; final diff review. | Complete; no production/test correction identified |

One atomic reviewed commit per necessary correction; a review-only result changes
only this register, CHANGELOG and HANDOFF. GUI-W1's stops remain binding; a
changed ownership, safety or verification boundary requires adjudication. The
regression study compares the old HDR selectors with the new WCG selectors,
traces envelope readers and native subscription cleanup, and checks retained
failure behavior. Historical GUI-D8–D10 diagnostics remain evidence, not a new
acceptance gate or authority to rerun compositor experiments.

Evidence: `build/wcg-review-20260924/` retains both installed attempts and
source/wheel/install identity records. The first gallery matrix attempt failed
the unchanged dark minimum-window clipping detector; the isolated rerun passed
without changed assertions. Both Advanced Color and HDR were active, so this
run does not isolate the WCG-only selector. GUI-W1's prior WCG-only and live
monitor-move evidence remains separate. No new compositor-health claim is made.

DOC-2 remains **pending, outside this M1-8 batch**: the historical branch
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
| M1-7 | Deliver bounded plan review, selection, execution admission, and the full plan consumer for sibling sorting. A review remains truthful when execution never ran; an admitted attempt keeps its selection committed. | Exercise plan publication, selection and commitment freshness, stale/replayed mutation, admission-failure rollback versus post-admission preflight refusal, fresh Plan-again review after source/target changes, destructive confirmation, controls, windows/anchors/search/filter, and headed production flows. No terminal selection reopening or subset retry. BRIDGE and PRESENTATION define protocol and projection criteria. | Complete |
| M1-8-capacity | Distinguish recognized disk-capacity I/O failure and stop admission of later executor operations after settling the current operation. | Gate C passed with A8-02's explicit recorder-only/finalization boundary; existing failure-policy/Stop and settlement paths, unchanged oracle. | Complete |
| M1-8 | Deliver live and retained execution review with bounded item windows, exact execution overlays, task/item recording issues, terminal axes, current ledger evidence, capacity/generic-I/O messages, and informational trash location. | Test filesystem/recording combinations, overlay and omission invariants, Gap plus terminal reconciliation, navigation/re-observation, generic unrun presentation, yellow capacity without hiding known failures, bounded evidence queries, and post-copy overlay independence. Trash counts require complete outcome evidence; location-only fallback must not assert a planned count, scan all trash, or imply purge. | A1–A5 verified; A6 receipt governs integrated closure. |
| M1-9 | Deliver bounded inventory projections, current evidence, and the full inventory consumer for sibling sorting. | Test complete or prior-complete publication, warnings outside action scope, raw evidence provenance, search/filter/collapse/window/detail behavior, replacement/races, supported sort/reset production paths, and headed witnesses. | Pending |
| M1-10 | Deliver baseline, verify, and rebaseline controls plus the first same-task manual post-copy verification without persistent operation-time hashes. Rebaseline includes eligible null-evidence files and always hashes/replaces evidence; matching content is not a verified match. | Test acknowledgement admission before claim/native work; all-null and mixed rebaseline through workflow, service/CLI, and desktop; conditional-recording and supersession races; handoff classification; live pause/resume/cancel and unchanged automatic failed-read retries; and overlay/result identity boundaries. Terminal Verify-remaining/subset retry is deferred. Independently review the operation matrix and conditional-recording races. | Pending |
| M1-12 | First close integrated lifecycle/retention across activated task surfaces (absorbing former M1-11), then complete adversarial, documentation, ordinary, and headed verification. | Exercise plan-only, execution-only, linked/manual verification, inventory, refused, canceled, degraded, and failed tasks across navigation, reinjection, explicit close, and shutdown. Verify existing admission bounds, stale-response suppression, exact resource release and retained result truth; no aggregate-artifact or whole-owner-graph criterion. Run applicable settlement-oracle stability, ordinary/headed suites, installed-wheel/product witnesses, import checks, `git diff --check`, active-link checks, and independent cross-component review. | Pending |
| M1-Release | Produce beta packaging and release closure after delivery rows above are complete. | Build/test an installed artifact from a clean checkout; supply frozen specification/dependency/CI, notices and corresponding-source release material, standard-integrity host proof, and every applicable BR-G and SH-G gate. INTERFACES owns host/package and SH-G release criteria; BRIDGE owns BR-G evidence. | Pending |


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

## M1-7 delivered

Delivered and integrated through `5986c57`: bounded Plan review and sibling
sorting, selection/commitment freshness, snapshot-bound destructive confirmation,
same-task execution, pause/resume/cancel, truthful committed-but-unrun review,
fresh Plan again and task-close/replay ordering. The browser keeps only its
bounded window; workflows/service remain authority for operations and effects.
BRIDGE, PRESENTATION, INTERFACES and DESKTOP_UI own current contracts. No
inventory/result-overlay or terminal retry/reopening was delivered by M1-7.

P9 accepted the unchanged `3c3bbbc` measured candidate: 35 metrics, 175 fresh
measurement children/775 samples after declared readiness, with independent
source/runtime/installed and terminal validation. Final ordinary verification
was 5,158 passed/four platform skips; imports, installed Plan checks, docs and
reconstructed integration accounting passed. Raw evidence and integration
receipt: `build/m1-7/evidence/p9-full-20260916/`; protected compact artifacts
remain at their existing paths in `tests/interfaces/web/`. This is the declared
Plan profile, not whole-app memory or current-source acceptance for later edits.

Post-delivery ablation R7-1–R7-4 landed through `95f31e1`; RI-1–RI-4 discovery
is complete. The suspended R7-5–R7-8/R7-G register is now retired, not completed;
useful proposals and evidence decisions are accounted under
[POST_M1_8_ABLATION](POST_M1_8_ABLATION.md#13-earlier-studies-absorption-and-archival-accounting).
No old R7 checkpoint resumes automatically or becomes a closure dependency.
Later delivered Plan GUI refinements
through `2cc0083` are recorded in the compact GUI results table above.

## M1-8 foundation delivered

| Closed row | Result and owner | Commit / accepted evidence |
| --- | --- | --- |
| M1-8-D | Condensed prior GUI records and established the original delivery register. | `42ff8f2`; documentation/link/diff review. |
| M1-8-capacity | Recognized disk-capacity operation/cleanup/prerequisite failures stop later admission after current settlement. Recorder-only failure remains independent degradation; finalization remains settlement. EXECUTOR owns classification. | `04947ba`; Gate C, unchanged 30-scenario/three-run settlement oracle, 5,216 ordinary passes/five skips, twelve import contracts. `build/m1-8-capacity-*-final01.log`, `build/m1-8-capacity-oracle-final.log`. |
| M1-8-E | Bounded atomic current-ledger classification, coherent content only, no schema/write path or full-run scan. DATABASE/PRESENTATION own evidence semantics. | `7905a1b`; Gate E, 5,226 ordinary passes/five unchanged skips and consumer/independent checks. `build/m1-8-e-ordinary-final01.log`, `build/m1-8-e-neighborhood-02.log`. |
| M1-8-P1 | Exact task/Plan/session/run-bound retained execution summary and separate operation/linked-verification indexes; capture before release; idempotent close/shutdown retirement. INTERFACES/PRESENTATION own lifetime. | `055325b`; Gate P1, 5,232 ordinary passes/five unchanged skips, neighborhood/independent/import checks. `build/m1-8-p1-ordinary-final02.log`, `build/m1-8-p1-neighborhood-01.log`. |
| M1-8-P2 | Bounded live/retained Plan summary/window overlays and one-operation detail, revision binding, visible Gap history and bounded current evidence. BRIDGE/PRESENTATION own protocol and measurement. | `4bbf943`; independent functional/installed/source review and full unmocked terminal/clean-HEAD validation. A8-03/A8-05 scoped Tier-2 window/start receipts accepted: p95/max 6.8/7.3ms and 58.8/65.1ms against unchanged 100/250ms. |

The immutable P2 artifacts remain reproducible at their recorded revision. The final U artifact supersedes corresponding performance results for the delivered UI bytes; historical failures and reconstruction dispositions remain in the evidence archive and [historical register](obsolete/M1_8_DELIVERY.md).

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
