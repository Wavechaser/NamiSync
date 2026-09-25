# Archived M1-7 / M1-8 working and recovery register

Historical snapshot taken on 2026-09-21 before closure-plan consolidation,
including the docs-only UI-I/UI-T investigations over product revision
`76f9281`. No permission, pending recipe or current-authority wording below
authorizes work. [The active register](../M1_PLAN.md) owns current scope.
Preserve this file as history; its copied statuses describe their own dates.

# M1 Delivery Register

This is the sole active M1 delivery register. It records remaining accepted outcomes, their order, and the verification that closes each one. Implemented contracts are owned by their active subject documents; completed delivery history and superseded mechanisms are in [obsolete](../obsolete). The archived plan files retain historical staging and review but are not instructions for new work.

[BRIDGE.md](../BRIDGE.md) owns external command, transport, retry/recovery, and bridge-gate contracts. [PRESENTATION.md](../PRESENTATION.md) owns trees, views, search, selection, sorting, and scale evidence. [INTERFACES.md](../INTERFACES.md) owns implemented task lifecycle and desktop host/package rules. [FEATURES.md](../FEATURES.md), [ARCHITECTURE.md](../ARCHITECTURE.md), and [DEFENSE.md](../DEFENSE.md) remain the owners of product behavior, cross-layer meaning, and safety/evidence policy.

[PRODUCTION_REDUCTION.md](PRODUCTION_REDUCTION.md) is the closed maintenance
subregister for the completed production-ablation pass under M1-12. Its PR-0
through PR-9 rows remove redundant implementation and test prescriptions; they
do not add, defer, or reinterpret an M1 product outcome.

## Main objectives and current boundary

The current authorized batch is **M1-8-capacity and M1-8**, starting at
`2cc0083` on `milestone1`. Implement and review smaller coherent commits,
then stop for a recap and GUI tweaks. M1-9 onward, DOC-2, push, PR and release
remain outside this batch. The user delegated stopping/scope adjudication to
the arbiter task `01a0ba9c-b187-70f1-bf21-4f91e742eeaf`; consult it on reached
boundaries and record its decision before dependent work resumes.

[REDUCTION_FOLLOWUP.md](REDUCTION_FOLLOWUP.md) owns the accepted narrow
immutable-value, scan-validation, history encoding/projection, and executor
simplification follow-up under M1-12. Its NR-0–NR-9 register and migrated RF-E/RF-X
dispositions preserve existing product outcomes; implementation and integrated
verification are complete. Further product simplification is outside the
remaining frontend delivery scope.

The secured desktop host and transport, presentation foundation, current service/CLI surface, and implemented ledger/history boundary are active. The frozen v1 event-and-transport custody claim remains closed at its bridge evidence owner. That closure does not establish whole-runtime containment.

The process-live desktop task shell, shared location admission and frozen Setup
are active, including plan/inventory starts and Plan again. M1-7 delivers bounded
Plan review, selection, sorting and reviewed execution admission. Finish execution/
inventory projections, integrity controls and first manual post-copy verification,
then release closure; those remain unrealized frontend outcomes. The history page, global-settings mutation
page, drag-and-drop, file-scoped planning, durable task survival across a process
restart, durable sort preferences, status/progress or global-flat sorting, and
compare-and-accept rebaseline semantics remain deferred. User-facing terminal
execution/verification retries (including Verify remaining), user-invoked session
cleanup/trash purge, and richer I/O error categories are deferred to M2; see the
feature-only [M2 proposal](../M2_PROPOSAL.md). Existing automatic retries, owned-temp
recovery, transport replay, close/shutdown recovery, and live pause/resume are
not removed by those deferrals.

The prior aggregate complete-owner-graph model and BR-G-45 are retired. No future work inherits its reservation, DTO, lease, byte-budget, command-count, or representation recipe. Completed M1-4 replaced the former task lifecycle/retention preservation checkpoint. Existing externally enforced ingress and population bounds remain active independently.

## Remaining checkpoints

### Completed GUI and documentation work

Completed records are condensed here; CHANGELOG and Git history through
`2cc0083` retain individual deliveries, studies, verification and exact diffs.
Active behavior belongs to the linked subject owners, not old implementation
populations or repeated test counts.

| Closed IDs | Delivered result / owner |
| --- | --- |
| GUI-1, GUI-S1–S3 | Task navigation, frozen Setup controls and Settings/About shell; independent rail/work scrolling and preserved task drafts. [DESKTOP_UI](../DESKTOP_UI.md). |
| GUI-S4–S12, GUI-R1–R2 | Origin-owned batch receipts, queued removal and settled-result clearing; compact tables with stable header/body gutters; native CSS scrollbar approximation; explicit smoke-only Ready witness; Fluent control and Setup refinements. [DESKTOP_UI](../DESKTOP_UI.md). |
| GUI-S13–S21 | Translucent Fluent control fills and authored 1.2px boundaries; keyboard/pointer textbox focus; pinned checkbox glyph; per-pair frozen options; sync-only batch projection. Keyboard, forced-color, exact retry and admission guarantees remain. [DESKTOP_UI](../DESKTOP_UI.md). |
| GUI-I1–I3 | Pinned local Fluent icon catalog, provenance, offline generation/checking and maintenance workflow. [TOOLS](../TOOLS.md). |
| GUI-D1–D7 | Shadow/disabled-label diagnostics and batch-housing study; M2 records for native overlay scrollbars, verify-only batching and persistent presets. [BUGS](../BUGS.md#desktop-material-composition), [DESKTOP_UI](../DESKTOP_UI.md), [M2_PROPOSAL](../M2_PROPOSAL.md). |
| AI-1–AI-2 | Execution/containment guidance and instruction condensation; component rules routed to their owners. AGENTS remains execution authority; personal-skill edits are separately recorded in CHANGELOG. |
| DOC-1, DOC-3 | Accepted frontend/M2 decisions reconciled across subject docs; completed history condensed and checkpoint expansion procedure established. Documentation verification did not claim product acceptance. |
| Plan-surface GUI-P1–P3 (2026-09-17) | Plan/Status cards, resizable rootless virtual table, sibling-sort gestures and exact byte display. `27f1a6b`, `4053a53`, `6425fa7`, `db46269`; component and installed Plan/gallery checks. [DESKTOP_UI](../DESKTOP_UI.md), [PRESENTATION](../PRESENTATION.md). |
| Scoped Plan GUI-S1–S3 (2026-09-17) | Revision-guarded header/folder selection over complete filtered membership, hidden selections preserved, synthetic root omitted. `f3bd84f`, helper correction `87dbd49`; ordinary/installed checks and 120,000-operation scoped-cost witness. These IDs are distinct from the earlier Setup GUI-S rows. [PRESENTATION](../PRESENTATION.md), [BRIDGE](../BRIDGE.md). |
| GUI-F1–F2, GUI-H1–H4 | Editable queued search, counted filters, stable panel/row refresh, server-owned highlights and atomic highlighted selection. `ae99f54`, `218866b`; ordinary, browser, installed and 120,000-row checks. The empty-rootless Setup witness noted in GUI-F was corrected during GUI-J. [PRESENTATION](../PRESENTATION.md). |
| GUI-J1–J3, GUI-K1–K3 | Grouped filters, compact viewport/task digest, neutral Plan-ready meaning, layout and status polish; directory own-operation eligibility corrected independently of descendant rollups. `44a5d49`, `4ef526e`, `f8bc1aa`, `0584707`; focused, department and installed default/larger Plan checks. Shared byte formatting was superseded by GUI-O below. [DESKTOP_UI](../DESKTOP_UI.md), [PRESENTATION](../PRESENTATION.md). |
| GUI-L1–L2 | Fluent control/gallery alignment and server-owned arrow navigation across windows, preserving pointer focus modality. `dd926b8`, `e6ee448`; component, interface and installed gallery/Plan checks. [DESKTOP_UI](../DESKTOP_UI.md). |
| GUI-M1–M2 | Status actions/feedback and static destination-tree folder totals from retained file facts; partial/overflow facts remain explicit, numeric sorting stays server-owned. `70a9270`, `7cf4448`; workflow/interface, independent scale-fixture sums, scalar boundaries and installed Plan checks. Historical scale receipts were not rewritten. [PRESENTATION](../PRESENTATION.md), [DEFENSE](../DEFENSE.md). |
| GUI-N, GUI-O, GUI-P (2026-09-19–20) | Friendly labels and selective low-risk notes, fixed semantic icon slots, immediate planning feedback, exact bytes below 1 KiB/two decimals above, tertiary text and final spacing/alignment. `c552537`, `8fd8cd0`, `2cc0083`; focused/department and installed gallery/default/larger Plan checks. [DESKTOP_UI](../DESKTOP_UI.md). |


GUI delivery evidence remains in the matching CHANGELOG tasks and those commits'
HANDOFF snapshots. Intermittent installed dialog/confirmation failures were
retained as failed attempts; unchanged isolated reruns passed without weakened
assertions. GUI-P's last evidence root is
`C:/Users/Spectrum/.codex/visualizations/2026/09/18/01a0b2ed-22b3-7083-a3e1-21f00596391d/`.
GUI-M2 recovery `af02913` and stash `93414b7` remain historical preservation,
not merge units; useful changes were rebuilt in `7cf4448`. The reported Optics
refresh delay remains unprofiled; no cloud/path diagnosis was established.

No rendering fix was established for the WCG shadow halo or intermittent
disabled-label blur. Mica remains required; no workaround or compositor-health
release gate was added. BUGS and DESKTOP_UI retain investigation boundaries and
reopen evidence. Recent availability remains observation, never admission.
The existing 48-pair bound, serial best effort, per-row options and exact
uncertain retry remain active; clearing receipts does not close tasks.

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
| M1-8 | Deliver live and retained execution review with bounded item windows, exact execution overlays, task/item recording issues, terminal axes, current ledger evidence, capacity/generic-I/O messages, and informational trash location. | Test filesystem/recording combinations, overlay and omission invariants, Gap plus terminal reconciliation, navigation/re-observation, generic unrun presentation, yellow capacity without hiding known failures, bounded evidence queries, and post-copy overlay independence. Trash counts require complete outcome evidence; location-only fallback must not assert a planned count, scan all trash, or imply purge. | Pending |
| M1-9 | Deliver bounded inventory projections, current evidence, and the full inventory consumer for sibling sorting. | Test complete or prior-complete publication, warnings outside action scope, raw evidence provenance, search/filter/collapse/window/detail behavior, replacement/races, supported sort/reset production paths, and headed witnesses. | Pending |
| M1-10 | Deliver baseline, verify, and rebaseline controls plus the first same-task manual post-copy verification without persistent operation-time hashes. Rebaseline includes eligible null-evidence files and always hashes/replaces evidence; matching content is not a verified match. | Test acknowledgement admission before claim/native work; all-null and mixed rebaseline through workflow, service/CLI, and desktop; conditional-recording and supersession races; handoff classification; live pause/resume/cancel and unchanged automatic failed-read retries; and overlay/result identity boundaries. Terminal Verify-remaining/subset retry is deferred. Independently review the operation matrix and conditional-recording races. | Pending |
| M1-12 | First close integrated lifecycle/retention across activated task surfaces (absorbing former M1-11), then complete adversarial, documentation, ordinary, and headed verification. | Exercise plan-only, execution-only, linked/manual verification, inventory, refused, canceled, degraded, and failed tasks across navigation, reinjection, explicit close, and shutdown. Verify existing admission bounds, stale-response suppression, exact resource release and retained result truth; no aggregate-artifact or whole-owner-graph criterion. Run applicable settlement-oracle stability, ordinary/headed suites, installed-wheel/product witnesses, import checks, `git diff --check`, active-link checks, and independent cross-component review. | Pending |
| M1-Release | Produce beta packaging and release closure after delivery rows above are complete. | Build/test an installed artifact from a clean checkout; supply frozen specification/dependency/CI, notices and corresponding-source release material, standard-integrity host proof, and every applicable BR-G and SH-G gate. INTERFACES owns host/package and SH-G release criteria; BRIDGE owns BR-G evidence. | Pending |


## M1-8 implementation register

Study baseline: `2cc0083`. Each row is a separate reviewed commit; dependencies
are serial. Root owns this register, CHANGELOG and HANDOFF. Builders own their
declared code, tests and subject docs. No product work starts on a later row
until its predecessor closes. Initial read-only studies found no mandatory stop.

| ID | Atomic outcome and finite population | Acceptance / state |
| --- | --- | --- |
| M1-8-D | Condense completed GUI records and register this batch; only M1_PLAN, CHANGELOG, HANDOFF. | Diff, links, outcome/limitation accounting and independent review passed; complete. |
| M1-8-capacity | Core execution reason and executor runtime classifier/default policy; executor runtime/settlement tests and direct core event/workflow-view/service consumers; EXECUTOR, FEATURES, DESKTOP_UI. | Gate C passed; complete. |
| M1-8-E | Bounded atomic current-ledger evidence query with read-only workflow/service facade and explicit evidence classes; existing db repository, workflow view contracts, runtime/service, matching repository/workflow/service tests; DATABASE, PRESENTATION, ARCHITECTURE, INTERFACES, FEATURES. No schema/recorder writes. | Gate E passed against integrated capacity `04947ba`; complete. |
| M1-8-P1 | Backend retained execution review: exact task/Plan/session/run binding, capture before release, separate operation and automatic linked-verification indexes, bounded workflow/service reads and close/shutdown retirement; workflow models/runtime and focused review owner, service/task lifecycle/port and direct tests; PRESENTATION, INTERFACES, ARCHITECTURE. | Gate P1 passed after E `7905a1b`; complete. |
| M1-8-P2 | Bounded summary/window/detail protocol over the existing Plan hierarchy; web Plan review/drain, commands/bridge and Python/browser validators with direct tests; PRESENTATION, BRIDGE, INTERFACES. | Complete in `4bbf943`; final independent review and full unmocked clean-HEAD binding passed. |
| M1-8-U | Live and retained execution UI, independent recording/terminal axes, capacity/generic-I/O guidance and location-only trash information; packaged app/Plan renderer/status/styles and browser/component/installed witnesses; DESKTOP_UI, FEATURES. | Incomplete at user-requested closure; implementation preserved on recovery branch. Installed/UI acceptance and U performance remain open; no merge. |

### Capacity boundary and gate C

The only production files are `namisync/core/execution.py` and
`namisync/modules/executor/runtime.py`. Add `disk-capacity` to the existing
ExecutionReason vocabulary; event-v5 derives its closed reason set from that
enum. Preserve event shapes/version, item-free terminal transport, independent
recording axes and all existing effect/settlement paths. Direct consumers are
`tests/test_executor_runtime.py`, `tests/test_executor_settlement.py`,
`tests/core/test_session_events.py`, `tests/core/test_event_v5_consumers.py`,
`tests/test_workflow_views.py` and `tests/test_service.py`; the direct native
preallocation consumer `tests/test_executor_native.py` must expect disk-capacity
for code 112 while preserving its cleanup assertions. Add witnesses only
where they exercise a distinct seam.

Recognize Win32 disk-full codes 39/112 and disk-quota code 1295, plus ENOSPC
when a native winerror is absent. Do not classify quota 1816, permission,
memory, socket quota or unknown errors as disk capacity. Native error codes
take precedence over errno. Trace actual explicit/semantic causal wrappers
with cycle protection; do not broaden sharing-violation retry classification
as a side effect. Preserve stronger existing typed reasons; only otherwise
generic I/O acquires the capacity label. Capacity policy uses existing Stop;
current-effect, cleanup, recorder-prerequisite and task-recording truth remain.

Regression study covers direct/wrapped capacity and native/errno precedence,
ordinary-I/O continuation, unchanged sharing retries, current pre/post-effect
settlement and recording combinations, and later independent/dependent work
left unrun by the policy-stop sweep. Gate C is these focused witnesses,
executor/core/workflows/interfaces neighborhood, ordinary suite, imports,
unchanged settlement oracle `check --repeat 3`, docs/diff checks and fresh
adversarial review. Baseline oracle passed 30 scenarios x 3 runs at `2cc0083`.
The oracle, baseline and semantic pin are immutable in this row. No settlement
redesign, native/pipeline changes, new taxonomy or frontend work belongs here.

**A8-02 — completed recurrence audit and authorized remedy.** Capacity can be
missed where failures bypass policy or cleanup introduces a new failure after
policy selection. Dependent edits paused; the arbiter approved this finite
correction before resumption. Production population remains the two files above.

| Reached path / owner | Consequence and disposition |
| --- | --- |
| MKDIR start / executor main loop | Direct settlement bypasses policy. Consult existing policy only for recognized capacity; accept Stop only, no new retries. Existing durable settlement and collaborator-escape path remain. |
| Pre-retry cleanup / executor main loop | Cleanup can introduce capacity after Retry was selected. Consult on the actual cleanup exception, preserve cleanup-failed wrapper/original cause, settle once, then stop only on Stop. |
| Ordinary failure cleanup / `_settle_ordinary_failure` | Continue/exhausted Retry can hide cleanup capacity. Return the transient cleanup exception after existing cleanup/settlement; only the admission-returning caller consults capacity policy. Escaping callers ignore it. |
| Other cleanup callers / BaseException, cancel, pause, backstop | These exit admission; no new Stop or settlement mechanism. |
| Deferred-directory finalization / executor | Already-admitted directories still settle/finalize; no new operation admission remains. |
| Recorder-only `_record` writes | Preserve filesystem success and independent recording degradation/continuation. No new stop field or exception retention. Pre-destructive recorder-prerequisite failure remains an operation failure eligible for Stop. |
| Final flush/restoration, workflow finish/close/open and preflight | Post-admission settlement or refusal before admission; preserve current axes and behavior. |

Original Stop dominates without another policy callback. Secondary Continue or
Retry never restarts settled work, sleeps, repeats cleanup or creates effects.
Non-capacity callback counts and MKDIR sharing/no-retry behavior remain unchanged.
Set stop only after successful settlement; preserve pause/cancel and callback
escape truth through existing paths. No settlement shape/trace/schema changes.
Add the distinct directory, ordinary/pre-retry cleanup, exhausted Retry, original
Stop, callback escape, recorder-only/prerequisite and non-capacity control
witnesses to Gate C. Native preallocation code-112 expectation migration is
also covered by A8-02. New findings beyond this table require containment anew.

Gate C closure: 3,968 consumer-neighborhood tests passed (two skips); 5,216
ordinary tests passed (five skips; 31 headed deselections). The five skips are
four unavailable symlink privileges and the unconfigured optional M1-7 readiness
artifact, not capacity gates. Latest test-only controls also passed independent
17-case focused review. The unchanged oracle passed 30 scenarios x 3 runs;
12 import contracts, 86 local documentation links, diff checks and fresh
adversarial review passed. No test or protected oracle artifact was retired.
Raw final logs are `build/m1-8-capacity-{neighborhood,ordinary}-final01.log`
and `build/m1-8-capacity-oracle-final.log`. Earlier temp-permission/source-tree
fixture runs are retained as failed attempts, not acceptance. Delivery is the
single `feat(executor): stop on recognized capacity failure` commit after
`42ff8f2`; the frontend remains pending.

### M1-8-E finite evidence boundary

Read-only study inspected `2cc0083` and the capacity candidate. Revalidate the
reason vocabulary against the integrated capacity commit before coding. E is
one stateless read model; task retention belongs to P1, web protocol to P2.

Production population: `namisync/db/repositories.py`, core evidence/execution
contracts only where genuinely shared, `namisync/workflows/models.py`, a focused
`namisync/workflows/execution_review.py`, runtime and workflow public exports,
and the forwarding method in `namisync/interfaces/service.py`. Existing db
public exports may change only as needed. No schema/index/recorder/history or
Plan projection changes. Reuse existing inventory/stat/attestation decoders.
Owning docs: DATABASE, PRESENTATION, FEATURES, INTERFACES and ARCHITECTURE's
source locator, plus this register/CHANGELOG/HANDOFF. Database supplies raw
snapshot facts; workflows classify them; interfaces do not decide attribution.

Admit an exact bounded tuple of at most 256 retained-operation subjects before
normalizing/deduplicating or opening SQL work. Resolve textual run token to its
internal row only inside one read transaction; batch requested operation tokens
and canonical target keys, using the run's target location. Repeated windows
must not scan/decode the whole run or inventory. Complete-run eligibility and
ambiguous target ownership are computed once by P1; E receives those trusted
facts, never a browser claim of evidence ownership. P1 separately proves their
derivation across off-window operations. No new latency/memory budget is added.

Only successful COPY/UPDATE/MOVE_UPDATE outcomes are eligible; an empty file
is eligible regardless of its zero byte count. Other outcomes/kinds are
not-applicable. No matching committed successful operation receipt means
unrecorded. A matching receipt without uniquely attributable coherent current
same-run target evidence is superseded, including ambiguity, missing/currently
absent row, changed scope, invalidation or contradictory observed/attested stat.
Coherent copy provenance with no verification timestamp is recorded-copy;
coherent readback/verify provenance with a verification timestamp is already-
verified. Only those two classes expose the stored xxh3_128 digest and its
provenance. Unsupported/incoherent combinations never borrow a digest. Preserve
item and task recording issues independently; a later task/audit failure does
not revoke a committed item. Do not promote failed post-publication outcomes
to successful evidence eligibility or infer authority from byte counts.

Finite verification: `tests/test_db_repositories.py`,
`tests/test_runtime_readers.py`, `tests/test_workflow_views.py`,
`tests/test_service.py` and a focused `tests/test_execution_review.py` assigned
in `tests/_departments.py` if needed. Witness all five classes, zero-byte copy,
linked readback/verify scope preservation, task recording degradation, absent
and mismatched receipt/run/target, duplicates/invalidated/superseded evidence,
native identity/stat coherence and no digest leakage. A trace/count witness
checks at most one run read, one bounded operation read and one bounded inventory
read per nonempty 256-subject window in one SQLite snapshot; first excess refuses
before SQL/materialization. Empty request behavior must be explicit and inert.
Reader reuse/error-retirement, affected database/workflow/interface/core checks,
ordinary suite, imports, docs/diff and fresh adversarial review close E. No
protected evidence artifact is changed. New schema, whole-run per-window work,
new ownership or attribution beyond these classes requires adjudication.

Gate E closure: final ordinary 5,226 passed, five unchanged capability/optional
artifact skips and 31 headed deselections; consumer neighborhood 2,960 passed,
one optional M1-7 artifact skip. Final focused and independent nine-case review
passed after correcting result-content validation and the closed-runtime empty
read. Twelve import contracts, 59 local documentation links and diff checks
passed. No protected artifact or test was retired. Raw logs:
`build/m1-8-e-neighborhood-02.log` and `build/m1-8-e-ordinary-final01.log`.
The initial neighborhood invocation used an invalid department name and ran no
tests. E's internal ownership bit remains trusted input until P1 derives it;
there is no browser evidence endpoint in this commit.

### M1-8-P1 finite retention boundary

Read-only study inspected `04947ba` and E's integration seams. Implementation
starts after E `7905a1b`, revalidating its models/runtime entry point.
This is A8-01's backend lifetime outcome, one atomic commit; P2 and U follow.

Production population: `workflows/{models,execution_review,runtime,__init__}.py`
and `interfaces/{service,task_lifecycle,task_port}.py` where the typed facade
needs forwarding. No dispatcher, core event, database, recorder, Plan construction
or hierarchy change. Subject owners are ARCHITECTURE, INTERFACES and PRESENTATION.
Tests are `test_execution_review`, `test_service`, `test_task_lifecycle`,
`test_runtime_readers` and `test_workflow_views`; the direct port fixtures in
`test_bridge_service` and `interfaces/web/test_drain` may migrate signatures
without changing behavior if the port changes. Root maintains this register,
CHANGELOG and HANDOFF.

Terminal dispatcher records have **no checkpoint**. Capture the exact immutable
core `OperationResult` from reconciled dispatcher truth before observer release,
dispatcher close, execution-detail drop or Plan retirement. Validate the exact
task association/Plan token against the service's existing committed artifact,
derived selection and execution session/run. The workflow retains the result
by reference, scalar binding and bounded operation/linked-integrity indexes;
no second hierarchy, checkpoint, observer or queue survives through this owner.
Expose item-free summary and exact at-most-256-operation reads. These internal
reads may share immutable item references; P2 must keep window summaries compact
and obtain full detail separately within the existing response byte bound.
An individual reliable event can reach 1 MiB, so blindly serializing 256 full
item details is not an acceptable public window. Missing items
remain unknown; emitted exclusion items retain their actual outcomes. Linked
verification is an independent index, bounded separately by Plan membership.
Reject foreign/duplicate result identities before publication.

Derive evidence ownership once from the complete committed selection: each
selected operation touches its canonical target; MOVE/MOVE_UPDATE also touch
their prior target. An eligible item's target is unique only when its touch
group contains that operation alone. Deduplicate one operation's same-key
touches. Unselected exclusions cannot compete; selected failed or missing items
still compete. This conservative implementation of A8-01 never infers content
ownership from a visible window or execution byte count. It adds no state or
effect policy to E. Record location-only trash context without filesystem reads.

Capture failure leaves settlement retryable before release effects. Repeated
capture is exact/idempotent; after partial cleanup removes dispatcher custody,
the existing terminal digest and retained binding/result permit retry. Release
retains review; successful task Close and completed shutdown dispose of it.
Failures before completed cleanup preserve the review for retry. Direct non-task
retirement stays unchanged. Do not infer a result from its item-free delivery
view, history or a later ledger read.

Gate P1: capture-order fault witnesses; stale task/session/run/token/selection
rejection; terminal-checkpoint absence; release/replay/Close and partial cleanup
retries; close/shutdown retirement and unchanged direct-session behavior; exact
axes/issues/omissions; separate automatic verification; off-window competing
targets, same-key move and excluded-versus-missing selected items; 256/first-excess
reads and Plan-bounded indexes. Run workflow/interface consumer departments,
ordinary suite, imports, docs/diff checks and fresh adversarial review. Existing
Plan representation/BR-G-42 evidence is untouched. Archived reopening, manual
verification, full browser lists, durable live results and history fallback
remain excluded. New ownership or effect changes return to the arbiter.

P1 delivered capture/retirement and the reads above without dispatcher or Plan
representation changes. Review corrected committed-decision reuse, linked
verification identity checks, exclusion ownership, an interface import route
and no-fail post-settlement retirement during shutdown. Gate: 2,532 workflow/
interface tests passed with one optional artifact skip; final ordinary 5,232
passed, five unchanged skips and 31 headed deselections (287.24 s). Final focused
review passed 244 tests; a subsequent test-only mixed-failure/axes/omissions
witness passed the 14-test review module and independent review. Twelve import
contracts, local links and diff checks passed. No existing test was retired.
Logs: `build/m1-8-p1-neighborhood-01.log` and
`build/m1-8-p1-ordinary-final02.log`. The earlier ordinary run collected an
intermediate new test expecting KeyError after runtime closing; its corrected
closed-runtime assertion passed focused review and the final ordinary run.

### M1-8-P2 protocol study and affected measurement boundary

Read-only study inspected E `7905a1b` and the P1 candidate; product implementation
starts after P1 `055325b`, refreshing its public reads and retirement.
P2 enriches the adapter's existing Plan summary/window, not PlanReviewState,
its projection, selection, ordering or visible sequence. Operation-bearing
containers receive the same overlay as operation leaves. Exact result detail
is a separate one-operation read; a 256-row window never expands full details.

Production population is `interfaces/web/{drain,commands}.py` and packaged
`assets/bridge.js`. Reuse the existing projection operation-ID mapping by
reference for live admission; do not copy another complete membership set.
Arm the execution epoch before returning the attach-before-start sink, preserve
the existing rollback/recovery binding, and bound operation and automatic
verification maps separately by Plan membership. Compact facts are replay
idempotent; do not use a generic sequence high-water to suppress replay.
Gap retains minimum/maximum observed `first_missed_seq` values, not a count or a
claim that every intervening sequence was lost. Terminal reconciliation uses
P1 facts and preserves that visible transport-loss history. Missing results
remain unknown. E alone supplies coherent stored digest/provenance.

Reads snapshot task/session/generation, Plan and execution revisions and the
requested operation IDs under the owner lock; workflow/ledger reads occur
outside it, followed by exact revalidation. No full-run scan per window,
history fallback, browser-owned complete result list, or altered action scope.
The existing 256-row and 8-MiB response walls remain; full detail keeps operation
and automatic verification distinct. P1's location-only trash context passes
through without filesystem reads. BRIDGE/PRESENTATION/INTERFACES own the
protocol and lifetime description; U owns rendering and interactions.

Direct tests are web `test_drain`, `test_commands`, `test_transport`,
`test_frontend_static`, `test_cosmetic_channel`, and the packaged bridge/drain
JavaScript probes. Exact command-catalog consumers also include `test_host`,
`test_native_host_gates`, `test_transport_headed`, `test_component_gallery_headed`,
`test_bridge_event_benchmark` and its root helper. Plan scale tests and benchmark
are compatibility consumers: migrate only actual adapter stubs/catalog facts,
never protected measurement semantics. Renderer-only legacy fixtures stay with
U unless an actual shared validator makes them a direct P2 consumer. Record
the final finite measurement helper/test/artifact names before their creation.
The one-operation detail wrapper has its own executable
`tests/assets/execution_detail_bridge_probe.mjs` witness; the existing
`task_shell_probe.mjs` is a direct exact command-policy consumer. These add no
renderer behavior or domain outcome.

Arbiter **A8-03** authorizes a separately identified scoped Tier-2 gate, not
renewed full M1-7/P9 acceptance. The selected metrics are
`ui_get_plan_window_one_row_receipt` and `ui_start_execution_receipt`: adapter
enrichment and pre-receipt live-epoch setup affect these timed paths even when
the extra work is constant. Each retains its existing installed full-base
fixture, untimed readiness/warmup, five fresh children with six samples each,
nearest-rank p95 <=100 ms and maximum <=250 ms. Record every failure/timeout,
exact child/sample membership, identities and dispersion. Do not substitute
successful retries for failed observations.

Component window/changed-view, construction and projection-memory metrics
directly own PlanReviewState paths/graphs and remain excluded only while those
are unchanged. Control receipt paths remain excluded only while their timed
dependencies are unchanged. Changes to those premises reopen their affected
cases without another scope pause; a changed measurement contract returns to
the arbiter. U must rerun any cases affected by its later measured-path edits.

Freeze independently checked source/instrument/validator/fixture/runtime/profile
and source-wheel-installed byte bindings, including newly reached dependencies,
before measurement. A separate scoped checker may reuse unchanged independent
validator checks; never filter the protected contract to pass its full terminal
validator with a partial collection. Require rejection controls for missing or
reused samples, wrong identities and max-only failure. Commit compact versioned
raw receipts/provenance and a separate validation result; ignored logs alone
cannot close Tier 2. Final committed product bytes must match measured bytes.
Existing contracts, budgets and historical evidence retain their meaning.
New overlay bounds close structurally without a new timing or memory claim.

The additive evidence population is `tests/m1_8_execution_receipt_benchmark.py`
(the two-metric adapter/collector),
`tests/interfaces/web/_m1_8_execution_receipt_scale.py` (independent scoped checker)
and its matching `test_m1_8_execution_receipt_scale.py`.
Use `m1_8_execution_receipt_{authority,receipts,result}.json` beside that checker
for frozen provenance, verdict-free raw observations and derived result. Exact
selected specs come from the unchanged compact M1-7 contract, not copied or
filtered authority. Reuse existing headed workload/readiness/child and authority
freezer primitives through the scoped adapter authorized by A8-05 below. Existing
per-receipt/profile/byte validators may be reused;
do not duplicate the headed workload or weaken its full-collection validator.
`tests/_departments.py` assigns the new test to interfaces. Temporary installs,
child outputs and logs stay in ignored `build/`; promote only the named compact
artifacts after independent verification. No new directory is needed.

Gate P2 combines live/terminal/Gap, fast-event admission/rollback/replay,
operation-bearing containers, independent verification, missing/omitted facts,
navigation/re-observation/reinjection, stale/Close/read races, 256/first-excess
and raw-byte bounds, no-DB preexecution fast path, literal hostile text and exact
Python/browser validators. Run interface/consumer checks, ordinary/import/doc
gates, installed headed command compatibility, the A8-03 scoped evidence and
fresh adversarial review before its atomic protocol commit. The evidence helper
may be built in an independently owned lane after P1 closes; its acceptance
remains coupled to the measured final P2 product, not a separate product claim.

Arbiter **A8-04** preserves independent review despite this task's agent-allocation
limit: a fresh GPT-5.6 Sol reviewer with no builder history runs in the arbiter's
separate agent tree. The arbiter coordinates the stable-candidate/raw-evidence
packet and final verdict. This is not a skill waiver or builder self-review;
P2 commit remains gated on that verdict and all named checks. Do not repeatedly
retry blocked allocations or disturb completed work to free slots.

Arbiter **A8-05** approves the finite measurement reorganization after a paused
three-finding review. The actual host service/registry/codec composition and
unmodified fixture controller creation, followed by public open/window, prove
120,000 projection nodes, 119,999 public rows and an independently derived
`NamiSyncPriorV1` Previous paths first group. Evidence and inspected hashes are in
`build/m1-8-rootless-controller-probe-2.log`; its script is
`build/m1-8-rootless-controller-probe.py`. This was untimed and headless, not
installed headed acceptance. The earlier unbound-codec setup failed before
publication; its partial ignored root is preserved.

| Finding / mechanism | Consequence and owner | Approved disposition |
| --- | --- | --- |
| Historical rooted fixture expectation | Old headed setup rejects the accepted rootless public surface; test fixture owner, not a product regression. | Scoped adapter and independent checker require exact source/public populations, 256-row current revision-zero/offset-zero settlement, per-plan identity and independently hashed prior-group first row. Preserve the start case's fresh unused Plan population. |
| Arbitrary well-formed authority OID | New helper could accept false artifact provenance; scoped evidence-custody boundary. | Derive embedded authority identity from declared canonical bytes; bind named authority through repository-filtered bytes and final HEAD comparison against raw evidence. |
| Missing durable launch/failure index | A disclosed-failure list cannot establish attempt accounting; same evidence-custody mechanism. | Publish the fixed 12-attempt plan and prelaunch state, then accepted receipt/path/hash/process or first failure/timeout/log evidence. Independently compare the final embedded index to raw observations. |

A8-05 resolves the repeated provenance mechanism and conservative three-finding
threshold together. It replaces A8-03's no-new-runner premise only for the named
two-metric adapter/collector; no generic runner, product patch, root fabrication,
historical producer/checker/contract/artifact edit or filtered full acceptance.
The ordered collection is two untimed readiness children (window, start), five
window children, then five start children. Stop on first failure; refuse restart
or overwrite, preserve its index/logs, and obtain disposition before another
collection. Launching, crashed, failed and incomplete indexes cannot pass. This
is evidence custody under the trusted local collection model, not resistance to
malicious rewriting. No acceptance children had launched at approval.

Version the scoped rootless report explicitly. Freeze the new adapter/checker/
test and product dependencies before measurement; both installed headed readiness
cases must pass. Add wrong-root/total/first-row, wrong well-formed OID, canonical
byte mutation, missing/reordered/duplicate/unlaunched attempt, receipt/hash
mismatch, reuse, incomplete/failure and overwrite/restart controls alongside the
existing sample/budget controls. Commit the compact final index with raw evidence,
retain separate derived results, and verify final clean-HEAD bindings. Changed
measured bytes invalidate affected observations. New findings outside this finite
remedy and mandatory safety stops still follow AGENTS containment.

The supplemental product bindings are `core/execution.py`,
`workflows/execution_review.py` and packaged `assets/{task_status.js,components.css,
tokens.css}`. The current start-submission render reaches task status through
rail/Plan review, and the real page loads both stylesheets; these are absent
from the historical compact manifest. Bind physical source, wheel member and
installed bytes for each. The scoped adapter/checker/test are source-only
dependencies; historical listed inputs remain fully bound.

Arbiter **A8-06** applies the recurrence rule to draft protocol defects and
authorizes this finite four-mechanism correction/review population within P2:

| Mechanism / owner | Candidate correction and required evidence |
| --- | --- |
| Post-release generation/publication ordering; drain release | Capture the publication generation after increment; successful retained read and transient summary-read retry. Preserve physical cleanup at-most-once through P1 owner evidence, not just fake lifecycle call counts. |
| Full detail work in compact windows; drain projection | Extract scalar operation/automatic-integrity facts without invoking or traversing full diagnostic conversion; one-operation detail still returns bounded detail and omission facts. |
| Mutable response aliasing; drain decoration | Copy returned operation/integrity facts and nested evidence content; mutation cannot change owned maps or later reads. |
| Valid foreign detail response; packaged bridge | Bind returned operation ID to the requested ID, including existing retry behavior; reject a structurally valid foreign response without weakening conflict/unavailable semantics. |

These corrections are not accepted until direct witnesses, existing Close/
reobserve/generation races, complete P2 gates and fresh frozen-candidate review
pass. No P1 redesign, feature, cache layer or generic serialization framework
is authorized. No supported data loss or false durable success was established;
no recovery full stop was required. A8-06 resolves this declared recurrence pause
only; another unplanned substantive instance requires renewed consolidated
adjudication before its remedy. Independent A8-05 work remains authorized.

Arbiter **A8-07** approves a test-only correction after the installed headed gate
passed 27 tests and failed four at stale exact command catalogs. Preserve
`build/m1-8-p2-headed-01.log`. The closed consumer audit corrects the earlier
synthetic-fixture exclusion: the event benchmark's real checker also consumes
its stale catalog. Update eight literal sites across
`tests/interfaces/web/test_native_host_gates.py` (two),
`tests/interfaces/web/test_transport_headed.py` (three),
`tests/bridge_event_benchmark.py` (one) and
`tests/interfaces/web/test_bridge_event_benchmark.py` (two), matching the current
28 production commands and each named test extension. Exact equality and all
security, origin, hostile-text, runtime and measurement assertions stay intact;
historical raw artifacts/contracts and acceptance claims remain unchanged.

The only additional control population is
`tests/interfaces/web/test_m1_8_execution_receipt_scale.py`: independently corrupt
synthetic-root/prior-group identity, public total and first-row semantics after
rehashing wrappers; exercise actual supplemental source/wheel/installed bytes;
and use real temporary Git blobs to prove clean-HEAD, dirty-source, source bytes
and named-authority/raw binding. Supplemental unit controls may isolate the
protected legacy parent validator, but actual freeze and terminal validation
must run both full historical and supplemental checks unmocked. A control that
exposes a validator defect requires adjudication before changing its helper.

Run focused catalog/control and department checks, then the four failed headed
tests on a fresh installed wheel with downstream assertions reached. Prior
unchanged-product ordinary/neighborhood and 27 headed passes remain evidence;
repeat broader tests only if changed shared seams invalidate them. Refresh
candidate hashes, imports/docs/diff and independent review before freezing.
Use a documented invocation of existing receipt/result/committed-source
validators, including staged-source checks before commit and full clean-HEAD
binding afterward. A failed terminal check leaves P2 incomplete. No product fix,
new metric, framework or weakened measurement/security contract is authorized.

Arbiter **A8-08** approves only advance U measurement elaboration: a separately
versioned report for all 13 existing installed-headed cases, eight cold cases
with five fresh single samples/max 50 ms and five warm cases with five children
times six samples/p95 100 ms/max 250 ms. Predeclare 13 readiness followed by 65
measurement attempts. Preserve P2 artifacts and all original endpoints/fixtures;
the scoped selection script may adapt its single 120000 total literal to 119999
only with an exact original-site/diff control. Component metrics remain excluded
only if their measured code/graphs stay unchanged. U still requires final P2
closure, refreshed finite population and fresh builder/reviewer before edits.

Arbiter **A8-09** stops before authority freeze or measurement because the
required no-unrelated-sustained-workload profile cannot currently be attested.
Two separated observations show persistent Code/Telegram CPU activity and an
active screensaver; this is a qualitative profile-premise conflict, not a new
CPU budget or failed timing result. No user process was changed. The arbiter
asked the user to quiesce the machine; the two-minute response window expired.
Task-owned P2 work is preserved on `codex/wip-20260920-0526-m1-8-p2`, based on
`055325b`. This recovery is not a merge unit and must not be merged/cherry-picked
as-is. HANDOFF and the recovery commit retain exact resumption provenance.

Candidate-02's 23-file manifest and patch remain in ignored `build/`, with fresh
independent prefreeze clearance and unchanged product/collector/checker bytes.
Ordinary 5263 passed/five existing skips; neighborhood 2564 passed/one existing
skip; 12 import contracts, 53 links, 41 scoped controls and 28 catalog checks
passed. Installed headed initially passed 27 and failed four stale catalogs;
the four corrected tests then passed on a fresh wheel. Preserve both logs.
No frozen authority, acceptance child, promoted raw/result artifact or final
P2 approval exists. Resume the same measurement obligation after actual profile
verification and source refresh; do not repeat unaffected passed gates or
start dependent U implementation. Historical evidence and later work remain
excluded. No automatic approval-review rejection caused this stop.

The user resumed and closed the identified applications. Observation-04 showed
the sustained workload absent; the arbiter lifted A8-09 on actual current
evidence, without changing profile or budgets. Reconstruct the reviewed named
population on `milestone1`, preserving recovery `015e782` until accounting and
integration finish. The user's subsequent instruction keeps P2 and U on that
recovery branch until verified, then merges the outcome series into `milestone1`
without squashing. Safety ref `codex/recovery-m1-8-p2-original-015e782` preserves
the original WIP; finalize only the single pending P2 commit after its gates,
then add separate U commits. No unverified WIP enters integration ancestry.
Arbiter **A8-10** approves the mechanical prefreeze identity refresh. The retained
per-path proof is `build/m1-8-p2-newline-proof.json`: original/current physical
SHA-256, reviewed/current filtered Git identities and normalized-byte equality.
Git checkout newline conversion is explicitly reconciled:
product bytes recover from the retained wheel only on exact reviewed SHA-256;
source-only adapter/checker/control bytes match their reviewed hashes. Remaining
test/doc newline-only differences retain identical filtered Git blob identities
and receive fresh physical bindings before measurement. No prior acceptance
children or artifacts exist to reuse.

Resumed collection `build/m1-8-p2/run-01` completed all 12 predeclared attempts
without failure: two readiness children and five fresh six-sample children per
metric. Independent raw validation reports window p95/max 6.8/7.3 ms and start
58.8/65.1 ms, inside the unchanged 100/250 ms limits. Full historical and
supplemental source/wheel/installed/runtime/profile checks passed before and
after collection. The named authority/receipts/result JSONs are promoted
byte-for-byte for final review; neither this scoped result nor later UI work
renews full M1-7 acceptance. Final evidence review and clean-HEAD binding remain
the terminal gate before U implementation.

P2 closed in `4bbf94366c987b35c7e3ad0d6333278fac9b01b5` after final independent
candidate-04 review. Full unmocked terminal workspace/raw/result/clean-HEAD
validation passed; `build/m1-8-p2/run-01/terminal-validation.log` retains output.
The 28-file reviewed candidate included 50 measured source bindings and three
artifact identities. Original WIP `015e782` remains under its safety ref.

### M1-8-U finite UI outcome and Gate U

#### U investigation and proposed restart (2026-09-21)

The user's renewed request authorizes investigation and options, not repairs,
acceptance changes or integration. Inspected revision: `76f9281`. Product/test
sources remain unchanged; historical implementation permissions remain stopped.

| Investigation / status | Finite corpus and method | Closure |
| --- | --- | --- |
| UI-I1 / complete | U's six changed production assets; parent/current CSS comparison in Edge with the real Plan renderer and existing 1,000-row probe fixture | Reproduce missing scrolling and offscreen Details; isolate final three-track CSS change without editing product |
| UI-I2 / complete | Headed05 log/packet, gallery specimen, short launcher and legacy page/native driver; ordinary frontend probes | Distinguish layout defect, prelaunch API mismatch and secondary driver timeout; identify missing layout coverage |
| UI-I3 / complete | CLI/launcher, retained review, command/drain and frontend tests; commit boundaries through P2 | 514 focused tests passed; retain backend/protocol work as restart candidates without declaring desktop acceptance |

No product fix, test rewrite, backend redesign, new acceptance matrix, full
headed rerun, performance run, commit, merge or recovery-ref cleanup belongs to
this investigation. Evidence is diagnostic, not a replacement for Gate U.

**Findings.** Edge 152 at 1280x800 gives the current 1,000-row body a 24,000px
client height equal to its scroll height; assigning scrollTop=240 leaves zero.
Details invokes the component callback but appears at y=24,420 beneath the
clipped work area. Loading only `HEAD^` CSS produces a 242px body viewport,
scrollTop=240 and Details at y=662. The diagnostic callback supplies a
not-retained response; this is not native detail-transport evidence. Script,
dimensions and visually inspected screenshots are retained under ignored
`build/m1-8-investigation*`; HANDOFF gives exact filenames and test invocation.

The minimum-layout gallery reuses an empty table (`total: 0`, `rows: []`), so
it cannot expose virtual-spacer intrinsic-height propagation. Ordinary DOM
fakes do not perform CSS layout; source-string assertions do not establish
scrollability. Both headed05 legacy driver records stop at `plan_surface`,
before `plan_offset`, with zero trusted input and confirmation stage `starting`.
The page next attempts the blocked scroll while the native driver waits for
later Execute readiness. This strongly connects those failures to scrolling;
the generic saved exception does not independently establish an ACK defect.
The short parent's `env=` differs from the shared launcher's `environment=`;
both short cases never launched.

**Recommendation, pending user decision.** Preserve capacity/E/P1 and verified
P2. Selectively reconstruct U from that foundation instead of merging WIP
ancestry or rewriting backend contracts. Revert the last CSS recipe only as a
starting point: it restores the reproduced behavior but not the previously
failing minimum-window layout. Prefer a compact summary and dedicated
scrollable detail surface; decide minimum-window/visibility behavior before
implementation. Preserve useful reducer/stale-response controls, test populated
rendered layout, reconcile the existing short launcher, and report the first
failed page phase instead of a later driver timeout. Then pass the existing
ordinary/import/installed gates, inspect required PNGs, and fulfill the existing
13/78 performance obligation before coherent reconstruction/integration.

#### Test-maintenance audit through 76f9281 (2026-09-21)

The user's follow-up authorizes a read-only test/DEFENSE audit, not cleanup or
changed acceptance. UI-T1 is complete: census every changed `tests/` path from
P1 `055325b` through `76f9281`, distinguish post-P2 changes, inspect direct
behavior tests, package identity, gallery/short/legacy witnesses and both scoped
benchmark stacks against DEFENSE sections 1, 4, 5 and 7 and their PRESENTATION
authority. This is a maintainability/evidence audit, not certification of every
assertion or renewed product acceptance. No new defect fixes or runs of the
installed/performance gates are authorized.

Census: 36 test-tree paths, 8,673 added/121 deleted lines since P1; 21 paths,
6,032 added/119 deleted since P2. These are diff observations, not quality
thresholds. `build/m1-8-test-audit.py` and `.json` retain the census and exact AST
comparison: 28 function pairs, 664 lines in the second copies, across the two
scoped validators, their tests and benchmark runners. Global metric/schema
constants differ; this supports shared parameterized mechanics, not blind
deletion or treating the two measured claims as identical.

| Population | Proposed disposition and reason |
| --- | --- |
| Command/drain, execution-detail/window bridge probes, execution result projection | Keep semantic coverage: exact binding, stale rejection, bounded windows, independent recording/integrity axes and capacity precedence protect supported product consequences. Consolidate data setup without deriving expected outcomes from production. |
| Task-shell/Plan component probes | Keep asynchronous ownership, navigation, refresh/scroll races and detail retirement. DOM fakes cannot certify CSS; move layout claims to a populated rendered witness. Small startup/setup/window fixture-shape migrations are necessary compatibility work. |
| Frontend static layout assertions | Replace recipe assertions (`fit-content`, diagnostic column variable/count, exact selector occurrence count) with outcome checks. Keep independently justified security/CSP/import guards. A valid alternative layout must not fail merely for different CSS syntax. |
| Gallery JS, child and parent | Keep theme, minimum native size, overflow/focus and truthful-status outcomes. Simplify the new diagnostic schema/transport controls at their owning boundary. The empty-table layout specimen must not stand in for virtualized-table behavior. Column-count assertions bind the current layout, not the user outcome. |
| Dedicated execution-review child and controls | Keep real copy/source preservation, correct task/operation, visible loaded detail, capture completion and cleanup. Simplify the roughly 300-line receipt/capture phase observer and synthetic transition controls. Exact-one detail read and permanently fixed view revision are fixture choreography, not general product requirements. |
| Native CDP and evidence paths | Keep shared UI-thread completion, standard PNG decoding/disposal and isolated per-case paths; these replace duplicated drivers and real evidence collisions. Do not discard them merely because the new launcher call is wrong. |
| Wheel identity and fixture integration | Keep clean staging and source/wheel/install equality with representative missing/extra/changed/duplicate-member controls. Consolidate repeated whole-population checks around identity-JSON writing; validate each meaningful build/install boundary rather than making provenance a repeated ritual. |
| P2/U benchmark validators, collectors and corruption tests | Keep budgets, raw observations, independent verdict, sample/runtime/source identity and failed-attempt retention. Consolidate duplicated mechanics in a versioned successor; preserve frozen historical validators/artifacts. Share fixture builders and representative corruption controls, not oracle/producer reasoning. |
| Rootless benchmark source-string adapter | Temporary compatibility shim is explicitly authorized, but byte-for-byte string rewriting and its matrix are maintenance debt. Retire through an explicitly versioned fixture interface when measurement ownership is reorganized, not by modifying protected history. |
| Command catalogs and department metadata | Keep current command availability and registration coverage. Repeated allowlists are a secondary consolidation candidate; do not derive the sole security oracle from the registry it checks. Existing legacy source-string guards are inherited debt, not all introduced by U. |

Two evidence labels need correction before reuse: the short witness's
`issuesKeyboardScrollable`/`detailKeyboardScrollable` test only tabindex;
its screenshot identity expression embeds observer run/session/revision
constants while reading task label/operation/detail visibility from the DOM.
The embedded values are receipt provenance, not independent rendered identity.
This does not prove a wrong screenshot occurred; neither short case launched.

DEFENSE was not absent from the written design: A8-03 and PRESENTATION explicitly
classify affected performance as Tier 2, preserve budgets/profile and repeated
fresh-process observations, and exclude unchanged metric populations. The repo
cannot establish how often the implementer read the policy. The policy supports
bounded ingress, truthful result axes, provenance and independent validators;
it does not require duplicated validators, exact CSS recipes or a second test
state machine mirroring every internal step. Lowering gates or deleting all
negative controls would be an unjustified opposite response.

Recommended restart adds a finite test-disposition map to U reconstruction:
for each removed assertion name its product consequence, replacement owner or
explicitly retired fixture constraint. First retain the known scrolling/Details
failure as independent behavioral evidence; then simplify the current harness
and layout together. Do not freeze broken product output as a golden baseline,
create another general framework, rewrite historical acceptance artifacts or
change the 13/78 obligation without a separate explicit decision. No numeric
test-reduction target is proposed. Gate U remains open.

#### Revised U verification register — stopped (2026-09-21)

**Current authority: FULL STOP AND RECOVER.** Headed05 rejected the scoped
allocation remedy: table usability passed, but readable body and reachable Close
failed. Both short cases failed prelaunch on the `env`/`environment` launcher
API mismatch; both legacy sizes failed Plan acknowledgement. Ordinary: 5,374
passed/five skipped; installed: 25 passed/eight failed. The arbiter permits only
exact preservation, no further implementation, diagnostic, gate, performance or
integration. The historical permissions below are consumed. HANDOFF owns the
compact mechanism table and unknowns; `build/m1-8-u-headed-05-packet/` preserves
the exact candidate/package identities and per-case evidence. This failed
allocation does not establish impossibility of every layout. Renewed authority
must precede further work; no acceptance expansion is requested.


Baseline: preserved failed candidate `9391a62`, safety ref
`codex/recovery-m1-8-u-headed04-9391a62`; verified P2 `4bbf943`.
The user-authorized redirection supersedes the previous UV implementation/run
permissions and fixed31 count. Historical decisions remain in `9391a62`;
HANDOFF points to exact failed evidence. Arbiter approval on 2026-09-21
authorizes this finite migration and one gallery diagnostic, with the
clarifications below. Product/U-F6 bytes stay frozen.

| Row / status | Closed outcome and ownership | Terminal gate / commit boundary |
| --- | --- | --- |
| UV-1 / independently verified, retained | Clean source/wheel/install identity; existing four-file package fixture outcome. | Existing parent evidence plus final combined gate; standalone package commit. |
| UV-2 / blocked after diagnostic | Identify gallery's reached measurement failure through one bounded light-mode diagnostic; retain corrected native callback and every layout assertion. No guessed remedy. | Closed reason/step/native snapshot identifies failed invariant; return diagnosis and any remedy to arbiter before implementation or another diagnostic. |
| UV-3 / approved migration | Separate short real-host execution-review scenario from the legacy 46-shell journey; one U phase owner and real plan/run identities. | Real-boundary controls, assertion map, both installed sizes and visually inspected persisted PNGs. Coherent U/UI/fixture commit with UV-4/5; no known-failing intermediate fixture commit. |
| UV-4 / retained legacy obligation | Preserve legacy capacity, navigation, reinjection, planning, confirmation, pause/resume/cancel, empty-plan and cleanup behavior. | Both legacy sizes and original Setup/acknowledgement witnesses pass in final installed suite; unresolved default earlier wait must be diagnosed if reproduced. |
| UV-5 / approved witness simplification | Native callback completion, standard PNG decoding, persisted capture then visible-identity recheck then ACK; replace syntax/synthetic-positive checks with actual wiring controls. | Negative controls fail at their intended boundary; harmless real variations pass; no handwritten PNG parser or duplicate native driver. Part of coherent U commit. |
| UV-6 / not run | Unchanged affected U performance contract: 13 cases, 78 attempts, exact accepted artifact. | Existing terminal metrics/identity validators and independent review; separately owned performance/evidence commit, clean-HEAD check, non-squash milestone1 integration. |

**Bounded diagnosis resumed (2026-09-21).** The user explicitly approved
"retry a bounded gallery diagnosis" from recovery `458a6f1`. The three existing
gallery files may retain the already-computed finite diagnostic-layout result
at its existing failure boundary, with representative transport control only.
Run exactly one light diagnostic under a new unique evidence root, remove its
temporary selector and report the reached predicate/cause with one remedy
proposal to the arbiter. No new acceptance criteria, production edit, speculative
fix, additional run or recursive fixture-test expansion is authorized. Existing
short-fixture/product bytes remain frozen. This approval supersedes only the
previous additional-diagnostic block; full acceptance remains outstanding.

**Bounded retry result.** The authorized second light diagnostic failed once
in 23.45 s. `native-minimum-all` had block size 513.714 and three visible
regions; only `table_usable` was false. All other thirteen existing predicates
passed, including root fit, horizontal controls, diagnostic scrolling/focus,
readable body and Close. Packet: `build/m1-8-uv2-diagnostic-packet-02`; temporary
selector removed and collection restored to four gallery cases. The reporting
change passed 22 ordinary controls. No acceptance or performance run follows
from this diagnostic.

Read-only tracing identifies an unreserved table viewport: content/table/list
tracks permit shrinkage to zero, while the existing gate requires one 24px row.
A scoped app.css allocation remedy reserves intrinsic table chrome plus one
existing row-height token, with diagnostics using bounded remaining space.
The arbiter approved this remedy below; its three track changes passed two
focused controls and independent source review. The ordinary suite passed
5,374 tests with five skips; imports kept all twelve contracts. Full clean
installed headed05 failed as recorded above; neither diagnostic is acceptance evidence.

**Scoped allocation remedy approved (2026-09-21).** The arbiter authorizes
`namisync/interfaces/web/assets/app.css` only to reserve intrinsic table
chrome/toolbar/header/scrollbar plus one existing `--file-row-h` viewport;
diagnostics yield within remaining bounded space. This lifts the product freeze
for that file only. Source population is its existing Plan content/table/list
track selectors; existing DESKTOP_UI and delivery docs record actual behavior.
The direct existing guard in `tests/interfaces/web/test_frontend_static.py`
pins the old track recipe; if replaced, update only that existing guard to the
chosen allocation. No new fixture matrix. Component benchmark inspection
confirms excluded projection/selection/memory paths are Python-only and their
code/retained graphs are untouched by this local CSS remedy.
No backend/interaction redesign, fixed pixel subtraction, larger window minimum,
hidden/truncated diagnostics, relaxed assertion or new predicate is authorized.
All thirteen passing minimum-layout predicates remain required. Incompatible
constraints require a design stop, not acceptance changes.

One coherent fix uses the unchanged focused/consumer, ordinary/import and full
clean installed gates (legacy/Setup plus both dedicated U sizes), followed by
required PNG inspection. No preliminary GUI or additional diagnostic is
permitted. On failure preserve/report; no automatic next repair. Once installed
acceptance passes, bind that artifact to the unchanged 13/78 performance gate,
then existing reconstruction/clean-HEAD/non-squash integration. Excluded
component metrics remain excluded if their code/retained ownership is untouched.
Keep both diagnostic packets and recovery refs. This is remedy scope, not a
waiver of acceptance.

**Frozen completion and current gallery stop (2026-09-21).** Direct user
steering freezes the agreed corrections and acceptance denominator: installed
scenarios, both U PNG inspections and existing performance verification.
Blockers need a concrete plausible supported failure, violated accepted
requirement or credible false-pass path; confidence-only improvements and
implausible extremes are deferred. Fixture controls are representative, not
an exhaustive diagnostic test matrix.

The one authorized light diagnostic failed in 25.28 s at
`measurement / native_minimum_layout / layout_invariant`, after passing native
minimum settlement/dimension validation. The existing aggregate layout check
retained no individual Boolean result; read-only tracing proves no specific
fixture or product cause and supports no guessed remedy. Exact source,
invocation, package identities and failure/final/log packet are in
`build/m1-8-uv2-diagnostic-packet`; original run is
`build/m1-8-uv2-light-diagnostic`. Temporary diagnostic selector was removed;
collection is again the four established gallery cases. Instrumentation's
22 ordinary controls passed, and the final Node timeout control passed once.
These are diagnostic/control results, not acceptance.

The arbiter reported automatic approval review rejected a second
instrumentation/diagnostic cycle as expansion beyond the frozen scope and
requested explicit user approval. Gallery edits, follow-up diagnostics and
remedies are paused pending that decision; no alternate route is authorized.
The independent six-file short-fixture corrective pass may finish its existing
source/control review boundary. Combined acceptance, performance and integration
remain blocked. Preserve exact task state on recovery; silence is not consent.

**Corrective-pass review (2026-09-21).** The first short-fixture candidate
failed source/control review before any GUI execution. Its shared causal
mechanism was copied assumptions about current evidence/native APIs and the
nondestructive execution path, compounded by synthetic controls that did not
exercise those owners. The arbiter authorized one consolidated corrective pass
inside the same six files: reconcile real publication/wait/final/cleanup APIs;
remove the destructive-modal branch; gate detail on matching released-session
and retained-window readiness; synchronize detached phase snapshots; prove
pre/post capture task/operation identity and native decode-to-ACK order. The
exact assertion map/regression study must precede edits and name only actual
controls, including real command/registry/service execution and queued native
callbacks. Return the stable candidate for independent review; no headed run
or second corrective chain is preauthorized. This is the required mechanism
reorganization, not permission for successive local fixes. Gallery's bounded
three-file diagnostic corrections remain independent.

**Short-fixture review closeout.** The approved corrective pass and four final
direct closures are complete at the source/control boundary: real task-row
selection/observed label, safe opaque failure identity, removal of source-order
sequence testing, and unconditional process cleanup. Actual service/registry/
command copy control passes. Root final focused gate: 15 passed/four headed
deselected (`build/m1-8-u-short-review-closeout.log`). The retired source-order
test is owned instead by the actual installed scenario and current phase/capture
assertions; no new synthetic suite. Exact final assertion ownership is retained
at `build/m1-8-u-assertion-map.md`. No short installed gate/PNG or U performance
has run. Preserve and stop with gallery unresolved; these checks are not delivery
acceptance and no further correction chain is preauthorized.

**Finite population.** UV-1 remains `tests/conftest.py`,
`tests/_wheel_identity.py`, `tests/test_wheel_metadata.py`, `docs/TESTS.md`.
UV-3/4/5 changes only the existing task-shell child and parent under
`tests/interfaces/web/`, adds `_headed_cdp.py`,
`_task_execution_review_headed_child.py`, `test_task_execution_review_headed.py`,
and assigns the new test module in `tests/_departments.py`. Existing
`_headed_native.py`, `_headed_evidence.py`, command extension and production
composition are reused unchanged. Do not import the legacy child into the new
scenario or create a mode that carries its 46-task state.
UV-2 diagnostic population is existing component-gallery child/parent and
`tests/assets/component_gallery/gallery.js`: one closed measurement-step/reason
vocabulary and, only for native-related failures, latest dimensions/pending
snapshot. No raw exception text, assertion relaxation or timeout extension.
Owning delivery docs are M1_PLAN/HANDOFF/CHANGELOG; update existing DESKTOP_UI
and PRESENTATION evidence sections on completion. Existing performance files
and protected contract remain as already declared below; no new metric scope.

**Scenario and state removed/reused.** Extract only existing native CDP
callback marshalling, evaluate/input dispatch and screenshot persistence into
`_headed_cdp.py`, shared by both drivers. Keep legacy phase policy local.
Remove its U-only Task49 receipt/detail/capture/ACK state and handwritten PNG
chunk/CRC validation. The short scenario creates one real task and a one-file
copy plan against an empty target through registry setup, performs the actual
native Execute interaction, then observes settlement, matching release,
retained-window adoption, one explicit detail request, persisted capture and
visible identity recheck in that order. This approved nondestructive fixture
avoids duplicating the legacy destructive-modal journey; legacy still proves
its refusal, modal and canceled header. Bind seeded plan id separately from
returned execution run/request and session ids; never assume a numbered label
or plan/run equality. Standard System.Drawing decoding follows native file
completion, with resource disposal; successful decoding precedes ACK and both
PNGs still receive visual inspection. Verify the intended target copy and
preserved source against known fixture bytes. Shared CDP owns transport, native
completion and persistence only; phases/domain observations stay local. One
bounded failure ends each scenario.

**Old-to-new assertion map.** This map is the migration denominator, not the
number of test functions. During implementation record exact old test/report
keys against their new owner before deleting any assertion.

| Existing outcome/assertions | Owner after migration |
| --- | --- |
| Initial rail/capacity, close/retry/navigation, busy/terminal release, reinjection | Legacy task-shell, unchanged expectations |
| Initial Plan rows/window/notices; execution refusal and unrun axes | Legacy task-shell |
| Plan-again changed source/target and capacity slot; optional trace safeguards | Legacy task-shell |
| Trusted keyboard/mouse, escape/focus/modal blocking/exit barriers | Legacy task-shell native confirmation |
| Pause, resume, cancel, `canceledExecutionHeader`; empty Plan geometry; Close/shutdown | Legacy task-shell |
| Seven execution-review geometry values: rootFits, tableUsable, rowHeight, issuesKeyboardScrollable, detailKeyboardScrollable, closeFocused, closeVisible | Dedicated U, default and larger; same expected values |
| Exact task/session/revision/operation, post-release window, loaded detail and visible Close | Dedicated U phase owner and real-boundary controls |
| U PNG persistence/decode, pre/post visible identity, PNG-before-ACK | Dedicated U native callback controls and both installed PNGs |
| Handler preservation, wrong identity/incomplete release/stale admission rejection, privacy/evidence isolation | Dedicated U controls; preserve original handler/effect semantics |
| Task49 literal, source-string/order assertions, handcrafted same-id positive receipts, handwritten PNG validity | Retire syntax/implementation constraints; replace with actual production command/registry/service positive path and native callback/decode controls |
| Architecture/security guards, installed provenance, bounded process cleanup, original Setup/ack tests | Existing owners; retain meaningful restrictions |

The issues tabIndex check proves an accessibility attribute even when the clean
success scenario has no visible issues panel; it does not prove visible
diagnostic reachability. Existing gallery owns visible issues/trash/detail
geometry. Do not manufacture a failure to populate the short success witness.
Before the single gallery diagnostic, controls must prove the allowlisted
reason/step survives JS, bridge, child, publisher and parent end to end; local
throw text alone is insufficient. Preserve its packet and return diagnosis plus
one scoped remedy to the arbiter before any remedy or further diagnostic.

Expected installed count is 33 (31 existing cases plus two short U cases),
subject to explicit collected-case mapping; neither count nor relocation may
hide lost outcomes. Shared native extraction must be exercised by both consumers.

**Real-boundary regression study and gates.** Positive identity control must
run actual production command/registry/service composition with distinct real
plan/run ids; a synthetic self-consistent record cannot prove this contract.
Controls cover wrong task/run/session/revision/operation, release not completed,
pre-release admitted window completing late, changed eligible current window,
native callback failure, invalid decoded file, premature ACK and postcapture
DOM change. Verify pass-through handlers called exactly once with original
arguments/results/errors. Keep independently clear U-F6 actual callback matrix
and native gallery scale-after-scheduling controls unchanged. Browser probes
exercise actual scenario expressions rather than source text ordering.

Run focused controls, affected consumer departments, ordinary suite/imports,
then full clean installed suite. UV-2 is a diagnostic run, never acceptance.
Final acceptance requires original legacy/Setup witnesses and both short U
PNGs; passing one cannot close another. Only then freeze the exact installation
and execute UV-6 once under its existing first-failure contract. Independently
review all changes, diff/links, assertion accounting and exact artifact identity.
Reconstruct coherent commits from P2 without WIP ancestry; preserve physical
measured bytes during final branch integration and revalidate clean HEAD.

**Stops/non-goals.** No backend/product rewrite, general test framework,
private app test API, asset rewriting, event suppression, retry/reopen loop,
benchmark recalibration or weakened deadline. Gallery cause remains unknown;
this approval authorizes diagnosis only, with one report back, not a patch/run
chain. New findings follow repository recurrence/safety rules and arbiter
adjudication. Keep failed packets, recovery refs and unrelated GUI/stash work.
After verified non-squash integration, stop for requested recap/GUI review.

Study refreshed against integrated P2 `4bbf943`: its summary/window/detail
shapes, execution revision, release and request correlation remain those read
during design. P2 production is unchanged from the measured reviewed candidate.
Deliver one coherent UI outcome with matching tests, owner docs and separately
identified affected measurement evidence; keep it separate from P2's commit.
Work stays on the user-requested recovery branch. Final integration is a normal
non-squash merge after U and combined verification, then stop for GUI recap.

Production population: `namisync/interfaces/web/assets/{app.js,plan_review.js,
plan.js,task_status.js,app.css,components.css}`. Reuse existing callbacks, inert
text rendering, tokens and Plan geometry. No backend/bridge contract, workflow
ownership, Plan projection/order/selection, icon catalog or theme redesign.
Root owns M1_PLAN, CHANGELOG, HANDOFF and the README phase summary; builder owns
DESKTOP_UI, FEATURES and the affected measurement section of PRESENTATION.

Use the coherent window execution header with its rows. Coalesce selected-window
refreshes; hidden tasks retain dirty state for selection, without complete
browser result lists or unbounded reads. Preserve task/session/review/action/
request/execution identities across scroll, navigation, reinjection and Close.
Release refreshes retained truth. Retain at most one explicitly requested full
operation detail and retire it on identity/revision change. Never expand detail
for every row or erase Gap history after terminal reconciliation.

Show operation and automatic verification independently, current stored evidence
only when coherent, recording issues and omission counts, and terminal axes/
phases/errors without collapsing degradation into success. Missing is unknown;
zero-byte successful activity ran. Capacity yellow requires that known failure
evidence supports it and cannot hide independent failures. Refused/unrun is
"Execution did not start", with committed selection and existing Plan again.
Trash is location-only, without count/existence/purge promises. No terminal
domain retry, manual verification, inventory, history or later-checkpoint UI.

Direct tests: `tests/interfaces/web/test_frontend_static.py`; existing assets
`plan_review_probe.mjs`, `setup_app_probe.mjs`, `app_startup_probe.mjs`,
`task_shell_probe.mjs`, `tree_probe.mjs` and `component_gallery/gallery.js`;
new `tests/assets/execution_review_probe.mjs` for the distinct execution matrix.
Dedicated U installed witnesses are `test_task_execution_review_headed.py` and
`_task_execution_review_headed_child.py`, sharing `_headed_cdp.py` with the
retained legacy `test_task_shell_headed.py` / `_task_shell_headed_child.py`.
Direct setup/component-gallery consumers remain
`test_setup_headed.py` and `test_component_gallery_headed.py`. Preserve existing
security/runtime/geometry assertions. Record newly identified direct consumers
before editing; this population does not authorize adjacent fixture cleanup.

The evidence population is `tests/m1_8_execution_ui_benchmark.py`,
`tests/interfaces/web/_m1_8_execution_ui_scale.py`, matching
`test_m1_8_execution_ui_scale.py` and
`m1_8_execution_ui_{authority,receipts,result}.json`. Assign only the actual new
test module in `tests/_departments.py`. Keep P2's adapter/checker/artifacts and
historical M1-7 source/contract/artifacts unchanged. A8-08 permits narrow reuse
of unchanged primitives, not generalizing the accepted P2 contract.

Predeclare the fixed case order from the unchanged compact contract: update-view,
mutate-selection, destructive-start, confirm, nondestructive-start, pause,
resume and cancel click-feedback; then one-row-window, start, pause, resume and
cancel receipts. Use all 13 separate untimed readiness children first, followed
by five fresh measurement children for each case in that order: exactly 78
attempts. Eight cold cases keep one sample/child and maximum <=50 ms; five warm
cases keep six samples/child, nearest-rank p95 <=100 ms and maximum <=250 ms.
Keep original fixtures, warmup, unused-Plan populations, endpoints and correctness.

The scoped rootless adapter retains 120000 projection nodes/119999 public rows
and independent first-group identity. Only selection-click's one original
`initialWindow.total !== 120000` literal may become 119999 through a script
adapter proving exactly one intended site and an otherwise identical script.
Never edit the protected original or rewrite observations. Bind all actual
source/JS/CSS/instrument/checker/control dependencies, wheel/installed/runtime/
profile bytes, and independently validate exact attempt/sample identities and
hashes. Carry forward A8-05/A8-07 provenance/corruption controls, including real
byte and clean/dirty Git tests. Publish the complete attempt plan before launch,
stop on first failure and refuse overwrite/restart or favorable substitution.
Actual collection begins only after source/control review on the final build.

Component construction/window/sort/selection/memory metrics remain excluded only
after the final U diff proves their measured code and retained graphs untouched.
This is affected headed revalidation, not full 35-case/P9 renewal or a new
execution-state latency/memory guarantee. Changed measured bytes reopen affected
observations; a changed measurement contract returns to the arbiter.

Gate U covers live/retained rows, zero-byte, partial/canceled/unrun, capacity-only
and mixed generic/integrity failures, recording/audit degradation, both omission
counts, missing/coherent/superseded/unrecorded evidence, hostile literal detail,
stale response/Close/reload, operation containers, bounded 256-row windows,
release refresh and persistent Gap. Require direct browser/real installed
witnesses, interface/workflow neighborhood, ordinary and complete installed
headed gates, imports/doc/diff, fixed affected evidence and fresh adversarial
review, followed by clean-HEAD evidence validation. Final integration must
preserve exact verified source identities or revalidate changed seams.

AGENTS mandatory safety and recurrence stops remain active, including draft
findings. New backend/bridge ownership/effect requirements need adjudication
before edits. No unverified WIP, excluded work or skipped acceptance criterion
may be hidden in the final merge. Fresh GPT-5.6 builder and separate fresh
reviewer are allocated through the arbiter's tree under the established route.

#### Preserved U findings and evidence

The detailed stop/resume and diagnostic chronology is preserved in recovery
`4642491` (M1_PLAN and HANDOFF), with the consolidated study at `d425589`.
Those historical run permissions are consumed or superseded by UV-1–UV-6.
Retain these product dispositions and regression obligations:

| Finding / decision | Preserved result and regression obligation |
| --- | --- |
| U-F1 / first selection | Guard absent prior detail ownership; initial/null selection must not crash. |
| U-F2 / refresh conflict | One existing forced reload, then quiescence on persistent conflict until an external trigger; no self-sustaining reads. |
| U-F3 / A8-11 navigation custody | Settings retires detail; request admission/completion/error/render retain navigation epoch and task/review/session/revision checks. Late replies cannot restore old detail or replace a newer request. |
| U-F4 / A8-12 and A8-15 diagnostic layout | Long issues and operation detail stay independently bounded/scrollable, alone and together, with usable table, unchanged row height and reachable Close at supported default/minimum sizes. Hidden panels consume no gap. No truncation or raised viewport minimum. |
| U-F5 / A8-13 capacity design | User chose yellow for both exact capacity-failed rows and run status. Aggregate capacity classification requires positive equal failed/capacity counts, integrity not-run/verified/baselined and recording/audit OK; stale windows cannot recolor newer terminal truth. Preserve literal failure and independent axes. |
| Mixed-capacity disposition | Supported mixed integrity failure is a separate successful/mismatched row plus capacity-failed row: aggregate stays red; exact capacity row stays yellow. A synthetic same-operation failed-copy/mismatch combination established no supported product defect. |
| A8-15 null-review regression | Initial null and populated-to-loading/error/null reset/hide prior issues, trash and detail; returning to current populated review restores only current content. Original failing and corrected reproducer retained. |

Source review cleared the A8-15 20-file packet plus its three-file delta.
Before this reorganization, ordinary was 5338 passed/five existing skips;
final interfaces was 1806 passed/one existing skip; twelve imports passed.
These are source evidence, not installed acceptance. Headed01 was 24/7 and
headed02 25/6; headed02 additionally failed its package-custody guard. The
unchanged-source eight stale wheel members, conftest alias mismatch, gallery
coordinate mismatch, wrong-task diagnostics and copied-script lexical failures
are now owned by the UV register, not separate patch/retry plans.

Observation02 proved current revision2 detail could load, but capture was
unreached after the diagnostic lexical error. The missing-detail wide PNG and
original Setup/ack failures are not closed by that observation. All raw packets,
failed artifacts, exact copies and hashes remain under build at the locations
in HANDOFF. The unrun replacement runner is preserved but is not the new gate
owner. No U performance collection has been accepted or run.

### Preserved boundaries for execution review

Keep committed selection after admitted preflight refusal; Plan again is the
recovery. Archived terminal-unrun reopening recipes do not apply. Indexed
follow, inventory UI, manual post-copy controls, terminal retry and purge stay
outside this batch. No history fallback, transient copy hash display, new
schema or complete trash scan. Use location-only trash information. Existing
automatic linked verification must remain a separate overlay.

New query/window/overlay bounds need source-derived enforcement and structural
witnesses over the admitted population, not M1-7's historical timings. Record
the exact domain and counts in PRESENTATION/DATABASE before implementation.
No new execution latency or memory budget is claimed. Changes to existing Plan
construction, representation, indexing, publication or windowing reopen their
affected BR-G-42 evidence; classify that seam before edits under DEFENSE §7.
Arbiter decision **A8-01** approves the necessary review lifetime extension:
retain the immutable core result by reference plus operation-keyed indexes in
workflow-owned review until task close. Capture and exact identity validation
precede custody release; capture failure cannot report release success. Repeated
capture/release/Close and partial-cleanup retries are idempotent, including when
dispatcher custody is already gone. Keep direct non-task retirement unchanged;
close and shutdown free review ownership without retaining queues/observers.
Live Gap may leave explicit uncertainty; terminal reconciliation restores only
facts in the exact result and never erases visible transport-loss history.
Missing/omitted facts are not invented success or unrun. P1/P2/U are separate
only where each preserves cleanup/public behavior; capture/retirement changes
remain atomic. DATABASE classification belongs to workflows, serialized by the
bridge. This is scope approval, not acceptance evidence; expand finite files
and update owning lifetime docs before P1 implementation.

All AGENTS mandatory and recurrence stops apply; route reached boundaries to
the designated arbiter with a finite proposal before dependent work resumes.

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

### Post-delivery ablation study (2026-09-16)

This discovery-only pass studies `ae3daf6^..5986c57`, starting from a clean
`5986c57` checkout. It authorizes no production/test changes, new acceptance
criteria, M1-8 work, push or PR. Work proceeds from diff/structure inventories
to selected behavioral seams and direct consumers, not exhaustive line review.
The original report, committed in `dbeb7a5`, distinguishes observed redundancy,
bounded experimental support and design proposals. Its successor
[implementation plan](M1_7_ABLATION_STUDY.md) retains that evidence and candidate
register; neither discovery nor plan preparation authorizes implementation.

| ID | Accepted study outcome | Named verification | Status |
| --- | --- | --- | --- |
| AB7-1 | Attribute checkpoint growth and map product/test/evidence owners. | Inclusive Git/AST census: 77 files, 22,273 additions; 72.3% of added lines in tests/helpers/evidence. | Complete |
| AB7-2 | Identify bounded architecture, logic and test ablations while preserving behavioral guarantees. | Twelve source/consumer-backed candidates with retained obligations and falsifying gates; E1 33/33 focused control/ablation passes, E2 5/5, and both deliberately seeded faults detected. | Complete |
| AB7-3 | Independently review with one Claude Opus 5 xhigh session and synthesize useful findings. | Two invocations of the same session, zero Claude subagents; targeted challenge accepted, corrected claims and useful recommendations synthesized. | Complete |
| AB7-4 | Deliver a ranked report and preserve exact review provenance. | Adversarial synthesis, documentation/link/diff checks, preserved review-start state, unchanged product/test tree; disposable copies removed. | Complete |

Finite corpus: the 77 changed files, their immediate symbol consumers and
owning active documents; earlier reduction dispositions are contextual evidence.
Stop discovery and report if supported hard-wall/data-loss/false-success
evidence is established; do not fix findings during this study. Other findings
are recommendations only. No benchmark rerun or performance claim is authorized
by static inspection. Evidence lives in ignored `build/m1-7-ablation/`: named
UTF-8 prompts/scripts, structural inventories, original-state receipt and raw
review responses. Preserve these for report provenance; disposable fixtures,
if needed, must be separately identified and removed after verification.

Both E1/E2 experiments used disposable copies and retained their exact plans,
patches and control/ablation/fault logs. E2's cohort-only patch is not suitable
for direct integration: any implementation must separate synthetic controls
from live-generator coverage. No full benchmark rerun, product/test edit or
commit was performed during discovery. The subsequent user-requested snapshot
commit is `dbeb7a5`; it preserves the original review reconciliation and usage.

### Post-delivery ablation implementation (2026-09-16 – 2026-09-17)

**Current direction (2026-09-17):** R7-1–R7-4 are delivered through `95f31e1`.
The user has suspended continuation to reassess substantial reductions of the
added test/evidence machinery; the production shell is not the target. The
ablation document's RI-1–RI-4 register now owns a read-only investigation,
including deferred retirement options. R7-5–R7-8 and R7-G remain unexecuted;
the earlier scope below is historical authorization, not an instruction to
resume. Proposed readiness/partial-index/tracer retirement, historical
archival and a simpler current acceptance path require a new decision before
implementation or evidence-policy changes. Existing SLOs and P9 meaning stay.

The user first requested a reviewed subtractive plan, then authorized execution
on 2026-09-17 after baseline and working-set preparation.
[M1_7_ABLATION_STUDY.md](M1_7_ABLATION_STUDY.md#checkpoint-register) is this
register's detailed maintenance subregister: R7-1–R7-8 and R7-G are the finite
accepted completion denominator before this reassessment.
Its candidate register preserves A1–A12 and explicitly separates selected
portions from deferred work. This does not reopen M1-7 product acceptance or
authorize M1-8, deferred redesigns, push or PR.

The selected scope is synthetic/live fixture separation, canonical-comparator
and unused replacement-route removal, independent-validator receipt checks,
producer publication bookkeeping, browser admission replay, lazy ID resolver
work and the tracer's mirrored test oracle. A5/A6/A7/A8/A10 remain deferred;
A4 read retries, broader A12 safety reuse and A11 tracer retirement are excluded.
A7 may be ratified later in ARCHITECTURE/PRESENTATION and this register.

Every row names its bounded behavioral population, protected guarantees,
product seams, detector-quality controls and atomic commit gate. Existing
product behavior is the baseline; green rewritten tests alone cannot prove
detector quality. Log/report latent product defects without fixing them in this
refactor. Introduced regressions remain checkpoint obligations; AGENTS stops
and DEFENSE consequence/evidence policy apply. The user-approved measurement
policy uses affected local Tier 1 checks before checkpoint commits and one full
current-source measurement suite at R7-G. Local checks do not renew full scale
acceptance; frozen budgets and historical artifacts remain unchanged.
PRESENTATION owns this scoped rerun policy; the subregister records exact gates.

### Delivered product scope and P9 closure

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

Behavior owners: [BRIDGE](../BRIDGE.md), [PRESENTATION](../PRESENTATION.md),
[INTERFACES](../INTERFACES.md), [DESKTOP_UI](../DESKTOP_UI.md), [FEATURES](../FEATURES.md).
[BUGS](../BUGS.md) records substantive corrected mechanisms. Core source remains the
authority for exact contract shapes; no dispatcher/module/db effect-policy change
was needed.

### Finite implementation and regression boundary

Production owners are core execution contracts; workflow tree/projection/selection helpers; existing
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

### Acceptance evidence and integration

The authorized P9 full run on the unchanged `3c3bbbc` candidate passed all
**35 fixed metrics**, after **15 readiness children / 35 untimed cases**, with
**175 fresh measurement children / 775 samples**. No retries, budget changes or
product changes were made during the run. Independent terminal, collection,
identity and physical-byte verification passed. This closes the quantitative
part of **M1-7-G**, alongside functional/consumer, ordinary, import, installed
headed, documentation and final integration checks.

| Evidence | Result |
| --- | --- |
| Six changed sorts | P95 0.756–1.109 s; largest maximum 1.192 s, within 1.5/3 s. |
| Review construction/staging memory | 280,768,512 bytes (267.762 MiB), within 320 MiB. This is not whole-app or paused-execution memory. |
| Confirmed execution admission receipt | P95 54.6 ms / maximum 55.4 ms, within 100/250 ms; receipt remains after admission. |
| Prior unchanged candidate verification | 5,157 ordinary tests, 259 checkpoint/resume/post-execution tests, 12 import contracts and installed Plan GUI passed at P8. |
| Final closure verification | 55 artifact/scale checks and 5,158 ordinary tests pass (four platform skips; 30 headed tests deselected). Documentation and reconstructed endpoint reviews pass. Clean committed-source, supplemental core and exact product/test accounting pass. |

Raw children, incremental indexes, readiness, authority, terminal measurements,
independent audit and before/after identities are retained under
`build/m1-7/evidence/p9-full-20260916/`. The current compact authority and
measurement artifacts are published at their contract-owned paths under
`tests/interfaces/web/`; previous bytes remain in Git and the evidence directory.
Authority SHA-256: `dcea9df79599739e07c8652b9a16eca6b7e88e81de31594c30bd74ec309797b7`.
Terminal artifact SHA-256: `e5718367c4f386e5845b93b7de484176228504b8382d0f6d5c0a1317d862665d`.
The fixed compact contract, historical legacy evidence and all budgets remain
unchanged. Legacy compatibility remains confined to the historical evidence reader.

The historical contract names 42 source, 38 installed and 14 runtime files.
P8's additional `namisync/core/execution.py` is bound separately by equal source,
installed and wheel-member SHA-256
`76350ca8aebb23959c47a502cb0767cfb569adf7cb45fdc1f80399b7df8ffbb9`,
checked before and after the full run and again at integration. The independent
audit verifies both this supplemental binding and the contract-owned population.
Collection receipt hashes are verified; per-child invocation/log hashes are not
fields of the full-run collection contract and are not claimed.

The reviewed closure series reconstructs six dependency-ordered outcomes from the
recovery history: reviewed Plan delivery and measurement readiness; covered
windows and compact Plan scale; reduced review/selection retention; prepared
selection digests; shared validated execution structure; and accepted evidence
with closure documentation. Intermediate trees preserve the historical failed
measurements honestly; only the complete verified series is merge-ready.
The original commits, including `cf5a00b` and `30d35f3`, are not amended or
integrated as WIP objects. Final product/test accounting against `3c3bbbc`
permits only the two newly accepted artifact files. Recovery history is preserved
by the `codex/m1-7-recovery-20260916` archive tag and the verified
`build/m1-7/evidence/p9-full-20260916/m1-7-recovery.bundle`. The integration receipt
in that directory records exact reconstructed and recovery commit identities,
tree equality, merge and branch cleanup. No original commit was amended.

The earlier confirmed hidden-control, state-ordering and Plan-retry defects are
closed at their existing owners; BUGS retains their mechanisms and witnesses.
Historical working records, failed runs and the bounded admission breakdown
remain in Git/evidence rather than this active register. Shared execution
structure extends one immutable index's paused lifetime; ARCHITECTURE owns its
complete retention account. No dispatcher policy or receipt guarantee changed.

Stop on `milestone1` after verified integration for the requested recap and GUI
review. M1-8, DOC-2, push, PR and release gates remain outside this task.

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
delivery fence; [BRIDGE](../BRIDGE.md) and [INTERFACES](../INTERFACES.md) own the active
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
[the archive](../obsolete/M1_6_SETUP.md). Exact commands, candidate hashes, raw
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

M1-8-capacity uses the existing failure-policy Stop and settlement paths for
recognized operation, cleanup and destructive-prerequisite capacity failures.
Recorder-only write errors retain independent degradation and continuation;
already-admitted directory finalization remains settlement. The finite A8-02
mechanism table and Gate C above own the implementation/verification boundary.
The unchanged retained oracle guards settlement; no capacity label may hide
an unrelated typed failure or recording issue. Frontend consumption follows
in M1-8, independently of this policy change.

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

Recognized operation, cleanup and destructive-prerequisite disk-capacity failure
stops later admission after current settlement under M1-8-capacity. Recorder-only
write failure remains recording degradation with continuation. Generic I/O keeps
its typed reason and needs ordinary frontend presentation.
Yellow capacity mapping uses existing DESKTOP_UI semantics and never hides
independent known failures. Trash-location text is accepted for M1; exact
counting is conditional on complete outcome evidence and display placement is
open. No filesystem inventory or purge is added to populate that information.

Location admission is workflow-owned and reused by typed, picker, and recent Setup/inventory inputs. A remembered location is not authorization; every consumer retains its point-of-use re-probe. Setup freezes its semantic plan options in a backend-derived snapshot and never writes global defaults or makes browser text/filter normalization authority.

Plan review must preserve operation, selection, scope, and fresh-preflight truth across view gestures. New views use canonical path-key order; filename, raw size, and raw mtime sorting in either direction and reset to canonical order are accepted M1 behavior. Sorting is process-live view state only and cannot alter selection, commitment, operation/dependency order, risk/counts, or action scope. It orders complete siblings before windowing and preserves node identity/hierarchy. Its exact protocol, validation, and scale evidence belong to BRIDGE and PRESENTATION.

Execution, inventory, and post-copy overlays stay distinct from each other and from ledger-derived state. A zero-byte activity that ran is never presented as unrun. Inventory warnings stay outside path/action scope and publication is complete or retains the prior complete generation. Baseline, verify, and rebaseline remain distinct operations. Rebaseline requires acknowledgement, includes eligible selected null-evidence files, replaces/creates evidence after a fresh hash, clears verification freshness, and does not become compare-and-accept. Manual exact post-copy verification uses an atomic handoff classification, works only on a ready subset, preserves original execution truth, and reports ineligible outcomes truthfully.

Release remains an accepted outcome. [INTERFACES.md](../INTERFACES.md#sh-g-release-criteria) owns the open SH-G-15 scoped cold-start and repeated/long-workload resource policy. It has no numeric budget or acceptance artifact yet; runtime request/population bounds and the separate SH-G-8 transport-custody evidence remain unchanged.

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

M1-4, M1-async (`675181a`), M1-5 (`e19ed9d`), GUI-1 (`b98dce4`), M1-6,
M1-7 and the subsequent Plan GUI work through `2cc0083` are delivered on
`milestone1`. The active batch is M1-8-capacity followed by M1-8; stop after
M1-8 for recap and GUI tweaks. HANDOFF owns immediate operational context;
AGENTS owns containment. Later checkpoints, halo workarounds, DOC-2, push and
PR remain unauthorized.
